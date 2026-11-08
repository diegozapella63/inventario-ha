"""O CorrerIA pelo HTTP, com o servidor de verdade: a chave CorrerIA (Mais > Configurações > Integrações) liga e desliga o
arquivo share/inventario/correria.json, as rotas GET e POST /api/integracao/ferramentas só abrem com a chave dele (401
desligado, com a chave errada ou com a dos outros apps), cada ferramenta lê ou grava (a rev sobe só nas gravações), os
erros vêm em {"erro"} (400 argumento, 404 ferramenta) e o último uso aparece para a tela (/api/data e /api/rev)."""
import json
import os
import re
import stat
import time
import unittest

from _boot import AppServer, ServerCase

ANA = {"id": "person.ana", "nome": "Ana"}


def esperar_arquivo(path, timeout=10.0):
    """Ao subir, o app grava os arquivos da pasta share numa linha à parte: espera por eles."""
    fim = time.time() + timeout
    while not os.path.exists(path) and time.time() < fim:
        time.sleep(0.05)
    return os.path.exists(path)


class Correria(ServerCase):
    def setUp(self):
        self.app.ok("PUT", "api/settings", {"correria": True})

    def tearDown(self):
        self.app.ok("PUT", "api/settings", {"correria": False})

    def info(self, app=None):
        with open((app or self.app).path("share", "correria.json"), encoding="utf-8") as f:
            return json.load(f)

    def h(self, app=None, cliente="CorrerIA"):
        return {"Authorization": f"Bearer {self.info(app)['chave']}", "X-App": cliente}

    def usar(self, nome, args=None, cliente="Claude", expect=200, app=None, pessoa=ANA):
        app = app or self.app
        st, _, out = app.post("api/integracao/ferramentas", {"nome": nome, "argumentos": args or {}, "pessoa": pessoa, "cliente": cliente},
                              headers=self.h(app))
        self.assertEqual(st, expect, out)
        return out

    # -- o arquivo e a chave
    def test_liga_e_desliga_o_arquivo(self):
        info = self.info()
        self.assertEqual((info["app"], info["nome"], info["ferramentas"]), ("inventario", "InventarIA", "/api/integracao/ferramentas"))
        self.assertRegex(info["chave"], r"^[A-Za-z0-9_-]{43,}$")
        self.assertTrue(info["url"].endswith(f":{self.app.port}"))
        self.assertEqual(stat.S_IMODE(os.stat(self.app.path("share", "correria.json")).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.app.path("data", "correria.key")).st_mode), 0o600)
        h = self.h()
        self.app.ok("PUT", "api/settings", {"correria": False})
        self.assertFalse(os.path.exists(self.app.path("share", "correria.json")))
        st, _, out = self.app.get("api/integracao/ferramentas", headers=h)
        self.assertEqual((st, out), (401, {"erro": "Chave inválida ou CorrerIA desligado no InventarIA."}))
        self.assertEqual(self.app.post("api/integracao/ferramentas", {"nome": "resumo"}, headers=h)[0], 401)
        self.app.ok("PUT", "api/settings", {"correria": True})
        self.assertEqual(self.info()["chave"], h["Authorization"][7:], "ligar de novo usa a mesma chave")
        self.assertEqual(self.app.get("api/integracao/ferramentas", headers=h)[0], 200)

    def test_opcao_so_verdadeiro_ou_falso(self):
        st, _, out = self.app.put("api/settings", {"correria": "sim"})
        self.assertEqual(st, 400)

    def test_chave_errada_ou_a_dos_outros_apps(self):
        with open(self.app.path("share", "integracao.json"), encoding="utf-8") as f:
            outra = json.load(f)["chave"]
        for valor in (f"Bearer {outra}", "Bearer errada", f"Basic {self.info()['chave']}", ""):
            with self.subTest(valor=valor[:12]):
                st, _, out = self.app.get("api/integracao/ferramentas", headers={"Authorization": valor} if valor else {})
                self.assertEqual(st, 401)
                self.assertIn("erro", out)
        st, _, _ = self.app.get("api/integracao/itens", headers=self.h())
        self.assertEqual(st, 401, "a chave do CorrerIA não abre as rotas dos outros apps")

    def test_fora_do_modo_dev_so_com_a_chave(self):
        app = AppServer(dev=False)
        self.addCleanup(app.stop)
        self.assertEqual(app.get("api/data")[0], 403)
        with open(app.path("data", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"correria": True}, f)
        app.stop(clean=False)
        app2 = AppServer(dev=False, root=app.root)  # reiniciado com a opção ligada: o arquivo volta sozinho
        self.addCleanup(app2.stop)
        self.assertTrue(esperar_arquivo(app2.path("share", "correria.json")))
        st, _, out = app2.get("api/integracao/ferramentas", headers=self.h(app2))
        self.assertEqual(st, 200)
        self.assertEqual(len(out["ferramentas"]), 8)

    # -- a lista
    def test_lista_no_formato_do_contrato(self):
        st, _, out = self.app.get("api/integracao/ferramentas", headers=self.h())
        self.assertEqual(st, 200)
        self.assertIn("inventario_resumo", out["instrucoes"])
        self.assertRegex(out["versao"], r"^\d+\.\d+\.\d+$")
        nomes = [f["nome"] for f in out["ferramentas"]]
        self.assertEqual(nomes, ["resumo", "buscar_itens", "ver_item", "cadastrar_itens", "editar_item", "mover_itens", "apagar_item", "novo_comodo"])
        for f in out["ferramentas"]:
            self.assertTrue(re.fullmatch(r"[a-z0-9_]{1,40}", f["nome"]))
            self.assertEqual(f["entrada"]["type"], "object")
            self.assertIs(f["entrada"]["additionalProperties"], False)
            self.assertIsInstance(f["grava"], bool)
            self.assertIsInstance(f["apaga"], bool)

    # -- as ferramentas
    def test_leituras_nao_mudam_a_rev(self):
        rev = self.app.ok("GET", "api/rev")["rev"]
        r = json.loads(self.usar("resumo")["texto"])
        self.assertEqual(r["itens"], 38)
        b = json.loads(self.usar("buscar_itens", {"texto": "tv"})["texto"])
        self.assertEqual(b["itens"][0]["codigo"], "SAL-007")
        v = json.loads(self.usar("ver_item", {"id": "SAL-007"})["texto"])
        self.assertEqual(v["valor"], 2300.0)
        self.assertEqual(self.app.ok("GET", "api/rev")["rev"], rev)

    def test_gravacoes_passam_pelas_regras_da_tela(self):
        rev = self.app.ok("GET", "api/rev")["rev"]
        txt = self.usar("cadastrar_itens", {"comodo": "Varanda", "itens": [{"nome": "Rede de descanso", "valor": 150}]})["texto"]
        m = re.search(r"id (var-\d+)", txt)
        self.assertIsNotNone(m, txt)
        iid = m.group(1)
        self.assertEqual(self.app.ok("GET", "api/rev")["rev"], rev + 1, "a tela vê a mudança pelo /api/rev")
        it = next(i for i in self.app.data()["items"] if i["id"] == iid)
        self.assertEqual((it["source"], it["createdBy"], it["value"]), ("correria", "Ana", 150))
        self.assertIn("valor: R$ 150 → R$ 180", self.usar("editar_item", {"id": iid, "valor": 180})["texto"])
        self.assertIn("Movido para Lavanderia", self.usar("mover_itens", {"ids": [iid], "comodo": "LAV"})["texto"])
        self.assertTrue(self.usar("apagar_item", {"id": iid})["texto"].startswith("Apagado: Rede de descanso"))
        self.assertFalse(any(i["id"] == iid for i in self.app.data()["items"]))
        self.assertEqual(self.app.ok("GET", "api/rev")["rev"], rev + 4)
        stored = self.app.stored()
        self.assertEqual(stored["rev"], rev + 4, "gravado no inventario.json")

    def test_novo_comodo(self):
        txt = self.usar("novo_comodo", {"nome": "Garagem de teste", "codigo": "GT"})["texto"]
        self.assertIn("código GT", txt)
        rid = re.search(r"id ([a-z0-9-]+)$", txt).group(1)
        self.assertTrue(any(r["id"] == rid for r in self.app.data()["rooms"]))
        self.app.ok("DELETE", f"api/rooms/{rid}")

    def test_erros_em_erro(self):
        out = self.usar("ver_item", {"id": "nada-999"}, expect=400)
        self.assertEqual(out, {"erro": "Item não encontrado: nada-999. Busque o id com inventario_buscar_itens."})
        self.assertEqual(self.usar("fotos", expect=404), {"erro": "Ferramenta desconhecida: fotos."})
        self.assertIn("Falta: id.", self.usar("ver_item", {}, expect=400)["erro"])
        st, _, out = self.app.post("api/integracao/ferramentas", {"nome": "ver_item", "argumentos": "sal-001"}, headers=self.h())
        self.assertEqual((st, list(out)), (400, ["erro"]))
        st, _, out = self.app.post("api/integracao/ferramentas", raw=b"{quebrado", headers=self.h())
        self.assertEqual((st, out), (400, {"erro": "Pedido inválido (JSON)."}))
        st, _, out = self.app.request("PUT", "api/integracao/ferramentas", {}, headers=self.h())
        self.assertEqual((st, list(out)), (404, ["erro"]))

    def test_ultimo_uso_para_a_tela(self):
        self.usar("resumo", cliente="Gemini")
        uso = self.app.ok("GET", "api/rev")["correria_uso"]
        self.assertEqual((uso["app"], uso["nome"]), ("Gemini", "resumo"))
        self.assertRegex(uso["em"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")
        d = self.app.data()
        self.assertEqual((d["settings"]["correria"], d["correria_uso"]["app"]), (True, "Gemini"))
        self.usar("buscar_itens", {"texto": "sofa"}, cliente="")
        self.assertEqual(self.app.ok("GET", "api/rev")["correria_uso"]["app"], "CorrerIA", "sem cliente: o próprio CorrerIA")
        self.app.ok("PUT", "api/settings", {"correria": False})
        self.assertIsNone(self.app.ok("GET", "api/rev")["correria_uso"], "desligado, a tela não mostra")

    def test_get_nao_conta_como_uso(self):
        self.usar("resumo", cliente="Claude")
        self.app.get("api/integracao/ferramentas", headers=self.h(cliente="Outro"))
        self.assertEqual(self.app.ok("GET", "api/rev")["correria_uso"]["app"], "Claude")


class UltimoUsoDepoisDeReiniciar(unittest.TestCase):
    def test_continua_depois_de_reiniciar(self):
        app = AppServer()
        self.addCleanup(app.stop)
        app.ok("PUT", "api/settings", {"correria": True})
        with open(app.path("share", "correria.json"), encoding="utf-8") as f:
            chave = json.load(f)["chave"]
        app.ok("POST", "api/integracao/ferramentas", {"nome": "resumo", "cliente": "Claude"}, headers={"Authorization": f"Bearer {chave}"})
        app.stop(clean=False)
        app2 = AppServer(root=app.root)
        self.addCleanup(app2.stop)
        self.assertEqual(app2.ok("GET", "api/rev")["correria_uso"]["app"], "Claude")
        self.assertTrue(esperar_arquivo(app2.path("share", "correria.json")))
        with open(app2.path("share", "correria.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["chave"], chave, "a mesma chave depois de reiniciar")


if __name__ == "__main__":
    unittest.main()
