"""Exportar, backup na pasta share, importar (de uma vez e em partes), versões anteriores e o primeiro uso."""
import csv
import io
import json
import time
import unittest
import zipfile

from _boot import ServerCase, b64, helpers


def send_in_parts(app, data: bytes, name="backup.zip", chunk=None):
    st, _, out = app.post("api/upload", {"name": name, "size": len(data)})
    assert st == 201, out
    uid, size = out["id"], chunk or out["chunk"]
    off = 0
    while off < len(data):
        part = data[off:off + size]
        st, _, r = app.request("PUT", f"api/upload/{uid}?offset={off}", raw=part, headers={"Content-Type": "application/octet-stream"})
        assert st == 200, r
        off = r["received"]
    return uid


class Exportar(ServerCase):
    def test_relatorio_em_pdf(self):
        """1.36.0: Mais > Relatório > Baixar PDF: o arquivo feito pelo servidor, com as fotos (ou sem), na cor do app."""
        st, h, raw = self.app.get("api/relatorio.pdf?fotos=1&cor=%23b48cf6&tinta=%237f56bb")
        self.assertEqual(st, 200)
        self.assertEqual(h["Content-Type"], "application/pdf")
        self.assertRegex(h["Content-Disposition"], r'attachment; filename="inventario-\d{4}-\d{2}-\d{2}\.pdf"')
        self.assertTrue(raw.startswith(b"%PDF-") and b"/Subtype /Image" in raw)
        st, _, raw = self.app.get("api/relatorio.pdf?fotos=0&cor=red")
        self.assertEqual(st, 200)
        self.assertNotIn(b"/Subtype /Image", raw)

    def test_planilha_json_e_zip(self):
        st, h, raw = self.app.get("api/export.csv")
        self.assertEqual(st, 200)
        self.assertIn("text/csv", h["Content-Type"])
        self.assertRegex(h["Content-Disposition"], r'attachment; filename="inventario-\d{4}-\d{2}-\d{2}\.csv"')
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(len(rows), 39)
        st, h, data = self.app.get("api/export.json")
        self.assertEqual(st, 200)
        self.assertEqual(len(data["items"]), 38)
        st, h, z = self.app.get("api/export.zip")
        self.assertEqual((st, h["Content-Type"]), (200, "application/zip"))
        names = zipfile.ZipFile(io.BytesIO(z)).namelist()
        self.assertIn("inventario.json", names)
        self.assertEqual(len([n for n in names if n.startswith("photos/")]), 9)
        self.assertEqual(self.app.get("api/export.pdf")[0], 404)


class Backups(ServerCase):
    def test_criar_listar_restaurar(self):
        lista = self.app.ok("GET", "api/backups")
        self.assertEqual((lista["backups"], lista["dir"], lista["available"]), ([], "share/inventario", True))
        st, _, out = self.app.post("api/backups")
        self.assertEqual(st, 201)
        nome = out["backup"]["name"]
        it = self.app.ok("POST", "api/items", {"room": "sala", "name": "Depois do backup"})["item"]
        out = self.app.ok("POST", "api/backups/restore", {"name": nome})
        self.assertTrue(out["safety"]["name"].startswith("antes-de-restaurar-"))
        self.assertFalse(any(i["id"] == it["id"] for i in self.app.data()["items"]))
        self.assertEqual(len(self.app.ok("GET", "api/backups")["backups"]), 2)
        for body, st_esp in (({"name": "../../etc/passwd"}, 400), ({"name": "nao-existe.zip"}, 404), ({}, 400)):
            self.assertEqual(self.app.post("api/backups/restore", body)[0], st_esp)


class Importar(ServerCase):
    def test_json_direto(self):
        data = {"rooms": [{"id": "r", "name": "Só um"}], "items": [{"id": "i", "room": "r", "name": "Item"}]}
        out = self.app.ok("POST", "api/import", {"data": data})
        self.assertEqual([r["name"] for r in self.app.data()["rooms"]], ["Só um"])
        self.assertEqual(self.app.ok("GET", "api/history")["history"][0]["reason"], "import")
        self.assertEqual(self.app.post("api/import", {"data": {"rooms": "x"}})[0], 400)
        self.app.ok("POST", "api/import", {"data": helpers.fixture_data()})
        self.assertEqual(len(self.app.data()["items"]), 38)

    def test_backup_zip_em_partes(self):
        data = helpers.fixture_data()
        data["items"][0]["name"] = "Sofá restaurado"
        data["items"][0]["photos"] = ["parte-a.jpg"]
        z = helpers.zip_bytes({"inventario.json": json.dumps(data), "photos/parte-a.jpg": helpers.jpeg(), "thumbs/parte-a.jpg": helpers.jpeg()})
        uid = send_in_parts(self.app, z, chunk=1000)
        info = self.app.ok("GET", f"api/upload/{uid}")
        self.assertEqual((info["kind"], info["items"], info["photos"]), ("backup", 38, 1))
        out = self.app.ok("POST", f"api/upload/{uid}/restore")
        self.assertEqual((out["replaced"], out["photosAdded"], out["items"], out["rooms"]), (True, 1, 38, 6))
        self.assertEqual(self.app.data()["items"][0]["name"], "Sofá restaurado")
        self.assertEqual(self.app.get("photos/parte-a.jpg")[0], 200)
        self.assertEqual(self.app.get(f"api/upload/{uid}")[0], 404, "o envio é apagado depois")

    def test_parte_so_com_fotos(self):
        rev = self.app.ok("GET", "api/rev")["rev"]
        z = helpers.zip_bytes({"photos/parte-b.jpg": helpers.jpeg()})
        uid = send_in_parts(self.app, z)
        self.assertEqual(self.app.ok("GET", f"api/upload/{uid}")["kind"], "photos")
        out = self.app.ok("POST", f"api/upload/{uid}/restore")
        self.assertEqual((out["replaced"], out["photosAdded"]), (False, 1))
        self.assertEqual(self.app.ok("GET", "api/rev")["rev"], rev, "não mexe nos itens")

    def test_envio_quebrado_fora_de_ordem_e_cancelado(self):
        z = helpers.zip_bytes({"inventario.json": json.dumps(helpers.fixture_data())})
        st, _, out = self.app.post("api/upload", {"name": "x.zip", "size": len(z)})
        uid = out["id"]
        st, _, r = self.app.request("PUT", f"api/upload/{uid}?offset=50", raw=z[:10], headers={"Content-Type": "application/octet-stream"})
        self.assertEqual((st, r["received"]), (409, 0), "parte fora de ordem diz onde parou")
        st, _, r = self.app.request("PUT", f"api/upload/{uid}?offset=0", raw=z + b"extra", headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(st, 400)
        self.app.request("PUT", f"api/upload/{uid}?offset=0", raw=z[:20], headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(self.app.post(f"api/upload/{uid}/restore")[0], 400, "o envio não terminou")
        self.app.request("PUT", f"api/upload/{uid}?offset=10", raw=z[10:], headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(self.app.ok("GET", f"api/upload/{uid}")["kind"], "backup", "reenviar a partir do meio funciona")
        self.app.ok("DELETE", f"api/upload/{uid}")
        self.assertEqual(self.app.get(f"api/upload/{uid}")[0], 404)
        for size in (0, -1, "x", 5 * 1024 ** 4):
            self.assertEqual(self.app.post("api/upload", {"size": size})[0], 400)
        self.assertEqual(self.app.get("api/upload/zzzz")[0], 404)

    def test_arquivo_que_nao_e_inventario(self):
        uid = send_in_parts(self.app, b"isto nao e um backup")
        self.assertEqual(self.app.get(f"api/upload/{uid}")[0], 400)
        st, _, out = self.app.post(f"api/upload/{uid}/restore")
        self.assertEqual(st, 400)
        self.assertIn(".zip", out["error"])


class Versoes(ServerCase):
    def test_lista_e_restaura(self):
        self.app.ok("POST", "api/items", {"room": "sala", "name": "Marca"})
        hist = self.app.ok("GET", "api/history")["history"]
        self.assertGreaterEqual(len(hist), 1)
        v = hist[0]
        self.assertTrue({"name", "date", "items", "rooms", "reason"} <= set(v))
        self.app.ok("POST", "api/history/restore", {"name": v["name"]})
        self.assertFalse(any(i["name"] == "Marca" for i in self.app.data()["items"]))
        self.assertLessEqual(len(self.app.ok("GET", "api/history")["history"]), 3)
        for body, esperado in (({"name": "../inventario.json"}, 400), ({"name": "inventario-20200101-000000.json"}, 404), ({}, 400)):
            self.assertEqual(self.app.post("api/history/restore", body)[0], esperado)


class PrimeiroUso(ServerCase):
    server_kw = {"seed": False}

    def test_vazio_ate_importar_ou_criar(self):
        d = self.app.data()
        self.assertEqual((d["rooms"], d["items"]), ([], []))
        self.assertEqual(self.app.post("api/items", {"room": "sala", "name": "x"})[0], 400)
        r = self.app.ok("POST", "api/rooms", {"name": "Sala"})["room"]
        self.assertEqual((r["id"], r["code"]), ("sala", "SALA"))
        out = self.app.ok("POST", "api/items", {"room": "sala", "name": "Primeiro item"})
        self.assertEqual(out["item"]["id"], "sala-001")
        z = helpers.zip_bytes({"inventario.json": json.dumps(helpers.fixture_data())})
        uid = send_in_parts(self.app, z)
        out = self.app.ok("POST", f"api/upload/{uid}/restore")
        self.assertTrue(out["safety"]["name"].startswith("antes-de-importar-"), "havia dados: guarda uma cópia antes")
        self.assertEqual(len(self.app.data()["items"]), 38)


if __name__ == "__main__":
    unittest.main()
