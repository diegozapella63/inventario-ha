"""Rotas da IA, do Falar e das fotos da internet pelo HTTP, com o servidor de verdade: /api/ai/status, /api/ai/identify,
/api/ai/usage, /api/ai/text, /api/voice/status, /api/voice e /api/web-photos*. Com a IA simulada do app (INV_AI_MOCK,
a mesma da prévia), com a IA desligada (Mais > Configurações > Integrações > Usar IA) e sem Home Assistant."""
import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from _boot import AppServer, FakeSite, ServerCase, helpers

OCTET = {"Content-Type": "application/octet-stream"}
PCM = b"\x01\x00" * 16000  # 1 segundo de áudio
VOICE_MIN = int(16000 * 2 * 0.4)
VOICE_MAX = 16000 * 2 * 125
DESLIGADA = "A IA está desligada. Para usar, ligue em Mais > Configurações > Integrações."
SEM_HA = "O app não tem acesso à API do Home Assistant."


def escrever_busca(pasta, resposta) -> str:
    return helpers.write_file(os.path.join(pasta, "busca.json"), json.dumps(resposta))


class IaCase(unittest.TestCase):
    def erro(self, method, path, body, status, msg, raw=None, headers=None):
        st, _, out = self.app.request(method, path, body, raw=raw, headers=headers)
        self.assertEqual((st, out.get("error") if isinstance(out, dict) else out), (status, msg), body)
        return out

    def uso(self):
        return self.app.ok("GET", "api/ai/usage")

    def esperar_busca(self, jid, app=None, timeout=20):
        app = app or self.app
        fim = time.time() + timeout
        while time.time() < fim:
            st, _, out = app.get(f"api/web-photos/{jid}")
            if st != 200 or out["stage"] != "busy":
                return st, out
            time.sleep(0.1)
        self.fail("a busca não terminou")


class Simulada(IaCase):
    """A IA simulada do app, com uma loja de mentira para as fotos da internet."""

    @classmethod
    def setUpClass(cls):
        cls.site = FakeSite()
        cls.pasta = tempfile.mkdtemp(prefix="inventaria-busca-")
        cls.app = AppServer(mock_ai=True, env={"INV_MOCK_SEARCH": escrever_busca(cls.pasta, helpers.search_answer(cls.site)), "INV_WEB_ALLOW_LOCAL": "1"})

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()
        cls.site.stop()
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def setUp(self):
        self.addCleanup(self.app.put, "api/settings", {"ai": True, "ai_entity": "", "ai_search": "", "voice_stt": ""})

    # -- estado e uso
    def test_estado_pronto_com_a_ia_simulada(self):
        st = self.app.ok("GET", "api/ai/status")
        self.assertEqual((st["ready"], st["reason"], st["selected"], st["search"]), (True, None, "", ""))
        self.assertEqual(st["entities"], [{"id": "ai_task.simulado", "name": "IA simulada (teste)", "attachments": True}])
        self.assertEqual([a["id"] for a in st["agents"]], ["conversation.simulado"])

    def test_estado_com_ia_escolhida_que_sumiu_usa_a_preferida(self):
        self.app.ok("PUT", "api/settings", {"ai_entity": "ai_task.sumiu"})
        st = self.app.ok("GET", "api/ai/status")
        self.assertEqual((st["ready"], st["selected"], st["missing"]), (True, "", "ai_task.sumiu"))

    def test_estado_com_a_ia_escolhida_e_a_da_busca(self):
        self.app.ok("PUT", "api/settings", {"ai_entity": "ai_task.simulado", "ai_search": "conversation.simulado"})
        st = self.app.ok("GET", "api/ai/status")
        self.assertEqual((st["ready"], st["selected"], st["search"]), (True, "ai_task.simulado", "conversation.simulado"))

    def test_uso_tem_7_dias_terminando_hoje(self):
        u = self.uso()
        self.assertLessEqual({"today", "week", "month", "days", "recent", "since", "sensor"}, set(u))
        self.assertEqual(u["sensor"], "sensor.inventaria_ia_hoje")
        self.assertEqual(len(u["days"]), 7)
        self.assertEqual(u["days"][-1]["day"], datetime.now(ZoneInfo(self.app.env["TZ"])).strftime("%Y-%m-%d"))
        self.assertEqual(set(u["days"][0]), {"day", "calls", "errors", "quota"})
        self.assertEqual(sorted(d["day"] for d in u["days"]), [d["day"] for d in u["days"]], "do mais antigo para hoje")

    # -- ler foto (Preencher com IA e Catalogar foto)
    def test_ler_foto_um_item(self):
        out = self.app.ok("POST", "api/ai/identify", {"file": "sala-1.jpg", "mode": "single", "room": "sala"})
        self.assertEqual(out["entity"], "ai_task.simulado")
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(set(out["items"][0]), {"name", "details", "cat", "qty", "value", "zone", "existing", "confidence"})
        self.assertEqual(out["items"][0]["name"], "Luminária de mesa articulada preta")

    def test_modo_desconhecido_vira_catalogar_e_conta_no_uso(self):
        antes = self.uso()["today"]
        out = self.app.ok("POST", "api/ai/identify", {"file": "sala-1.jpg", "mode": "outro"})
        self.assertEqual(len(out["items"]), 3)
        depois = self.uso()
        self.assertEqual(depois["today"]["calls"], antes["calls"] + 1)
        self.assertEqual(depois["today"]["images"], antes["images"] + 1)
        self.assertEqual(depois["today"]["kinds"].get("catalogo", 0), antes["kinds"].get("catalogo", 0) + 1)
        self.assertEqual({k: depois["recent"][0][k] for k in ("kind", "entity", "result", "images")},
                         {"kind": "catalogo", "entity": "ai_task.simulado", "result": "ok", "images": 1})

    def test_ler_foto_sem_foto_que_exista_recusado(self):
        for body in ({}, {"file": ""}, {"file": "nao-existe.jpg"}, {"file": "../inventario.json"}, {"file": "sala-1.gif"}):
            with self.subTest(body=body):
                self.erro("POST", "api/ai/identify", body, 400, "Envie uma foto antes de pedir a leitura por IA.")

    def test_dica_acima_de_300_recusada(self):
        self.erro("POST", "api/ai/identify", {"file": "sala-1.jpg", "hint": "h" * 301}, 400, "O campo dica passou do limite de 300 caracteres.")

    def test_pedido_recusado_nao_conta_no_uso(self):
        antes = self.uso()["today"]["calls"]
        self.app.post("api/ai/identify", {"file": "nao-existe.jpg"})
        self.app.post("api/ai/text", {"text": ""})
        self.assertEqual(self.uso()["today"]["calls"], antes)

    # -- o que foi falado vira itens
    def test_texto_falado_vira_itens_com_o_valor_dito(self):
        out = self.app.ok("POST", "api/ai/text", {"text": "Sofá cinza, dois mil reais. Televisão de 55, três mil. Duas luminárias de chão."})
        self.assertEqual(out["room"], "")
        self.assertEqual([(i["name"], i["value"], i["qty"]) for i in out["items"]],
                         [("Sofá cinza de três lugares", 2000, "1"), ("Televisão Samsung 55 polegadas", 3000, "1"), ("Luminária de chão", 300, "2")])

    def test_texto_falado_conta_como_fala(self):
        antes = self.uso()["today"]["kinds"].get("fala", 0)
        self.app.ok("POST", "api/ai/text", {"text": "uma cadeira"})
        self.assertEqual(self.uso()["today"]["kinds"]["fala"], antes + 1)

    def test_texto_vazio_ou_longo_recusado(self):
        for text, msg in (("", "Preencha o campo texto."), ("   ", "Preencha o campo texto."), (None, "Preencha o campo texto."),
                          ("t" * 4001, "O campo texto passou do limite de 4000 caracteres.")):
            with self.subTest(text=str(text)[:10]):
                self.erro("POST", "api/ai/text", {"text": text}, 400, msg)

    # -- Falar: fala para texto
    def test_falar_pronto_com_a_fala_do_assistente(self):
        st = self.app.ok("GET", "api/voice/status?fresh=1")
        self.assertEqual({k: st[k] for k in ("ready", "engine", "language", "name", "assistant", "selected", "missing")},
                         {"ready": True, "engine": "stt.simulado", "language": "pt-BR", "name": "Fala simulada (teste)",
                          "assistant": "Assistente simulado", "selected": "", "missing": False})
        self.assertEqual([e["id"] for e in st["engines"]], ["stt.outra", "stt.simulado"])

    def test_falar_com_a_fala_escolhida(self):
        self.app.ok("PUT", "api/settings", {"voice_stt": "stt.outra"})
        st = self.app.ok("GET", "api/voice/status")
        self.assertEqual((st["engine"], st["name"], st["assistant"], st["language"], st["selected"]),
                         ("stt.outra", "Outra fala (teste)", "", "pt-BR", "stt.outra"), "mudar a opção já vale, sem esperar o minuto")

    def test_falar_com_a_fala_escolhida_que_sumiu_volta_para_a_do_assistente(self):
        self.app.ok("PUT", "api/settings", {"voice_stt": "stt.sumiu"})
        st = self.app.ok("GET", "api/voice/status")
        self.assertEqual((st["ready"], st["engine"], st["missing"], st["selected"]), (True, "stt.simulado", True, "stt.sumiu"))

    def test_audio_vira_texto_com_a_fala_usada(self):
        out = self.app.ok("POST", "api/voice", raw=PCM, headers=OCTET)
        self.assertEqual((out["engine"], out["name"]), ("stt.simulado", "Fala simulada (teste)"))
        self.assertTrue(out["text"].startswith("Sofá cinza"))

    def test_audio_curto_demais(self):
        for pcm in (b"", b"\x00" * (VOICE_MIN - 1)):
            with self.subTest(bytes=len(pcm)):
                self.erro("POST", "api/voice", None, 422, "Não ouvi nada. Toque no microfone e fale.", raw=pcm, headers=OCTET)

    def test_audio_de_mais_de_2_minutos(self):
        self.erro("POST", "api/voice", None, 413, "Fale até 2 minutos de cada vez.", raw=b"\x00" * (VOICE_MAX + 2), headers=OCTET)

    def test_audio_muito_maior_recusado_sem_guardar(self):
        self.erro("POST", "api/voice", None, 413, "Arquivo grande demais.", raw=b"\x00" * (VOICE_MAX + 1025), headers=OCTET)

    def test_transcrever_nao_conta_como_chamada_de_ia(self):
        antes = self.uso()["today"]["calls"]
        self.app.ok("POST", "api/voice", raw=PCM, headers=OCTET)
        self.assertEqual(self.uso()["today"]["calls"], antes)

    # -- fotos da internet
    def test_busca_com_fotos_e_dados_do_produto(self):
        st, _, out = self.app.post("api/web-photos", {"name": "Cafeteira", "details": "inox", "qty": "1"})
        self.assertEqual((st, set(out)), (202, {"id"}))
        self.assertRegex(out["id"], r"^[0-9a-f]{16}$")
        st, res = self.esperar_busca(out["id"])
        self.assertEqual((res["stage"], res["msg"]), ("done", ""))
        self.assertEqual(res["product"], {"name": "Cafeteira Espresso Exemplo CX-20", "details": "Cafeteira espresso de 15 bar, inox, reservatório de 1,2 L.",
                                          "cat": "cozinha", "value": 450})
        self.assertEqual([r["n"] for r in res["results"]], list(range(len(res["results"]))))
        for r in res["results"]:
            self.assertEqual(set(r), {"n", "kind", "image", "page", "site", "w", "h"})
            self.assertIn(r["kind"], ("jpeg", "png", "webp"))
            if r["w"] is not None:
                self.assertGreaterEqual(min(r["w"], r["h"]), 200, "foto pequena fica de fora")
        self.app.ok("DELETE", f"api/web-photos/{out['id']}")

    def test_foto_da_busca_servida_sem_cache_com_o_tipo_dela(self):
        jid = self.app.ok("POST", "api/web-photos", {"name": "Cafeteira"})["id"]
        self.addCleanup(self.app.delete, f"api/web-photos/{jid}")
        _, res = self.esperar_busca(jid)
        tipos = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        for r in res["results"]:
            with self.subTest(n=r["n"]):
                st, h, img = self.app.get(f"api/web-photos/{jid}/{r['n']}")
                self.assertEqual((st, h["Content-Type"], h["Cache-Control"]), (200, tipos[r["kind"]], "no-store"))
                self.assertGreater(len(img), 3000)

    def test_busca_conta_no_uso(self):
        antes = self.uso()["today"]["kinds"].get("busca", 0)
        jid = self.app.ok("POST", "api/web-photos", {"name": "Cafeteira"})["id"]
        self.addCleanup(self.app.delete, f"api/web-photos/{jid}")
        self.esperar_busca(jid)
        self.assertEqual(self.uso()["today"]["kinds"]["busca"], antes + 1)

    def test_busca_nome_obrigatorio_e_limites(self):
        for body, msg in (({}, "Preencha o campo nome."), ({"name": "  "}, "Preencha o campo nome."),
                          ({"name": "n" * 201}, "O campo nome passou do limite de 200 caracteres."),
                          ({"name": "Cafeteira", "details": "d" * 4001}, "O campo detalhes passou do limite de 4000 caracteres.")):
            with self.subTest(body=str(body)[:40]):
                self.erro("POST", "api/web-photos", body, 400, msg)

    def test_busca_que_nao_existe_mais(self):
        for path in ("api/web-photos/0123456789abcdef", "api/web-photos/0123456789abcdef/0"):
            with self.subTest(path=path):
                self.erro("GET", path, None, 404, "Esta busca terminou. Busque de novo.")

    def test_foto_fora_da_lista_da_busca(self):
        jid = self.app.ok("POST", "api/web-photos", {"name": "Cafeteira"})["id"]
        self.addCleanup(self.app.delete, f"api/web-photos/{jid}")
        _, res = self.esperar_busca(jid)
        self.erro("GET", f"api/web-photos/{jid}/{len(res['results'])}", None, 404, "Foto não encontrada.")

    def test_codigo_da_busca_fora_do_formato_nao_e_rota(self):
        for path in ("api/web-photos/XYZ", "api/web-photos/0123456789abcdef/10", "api/web-photos/0123456789abcdef/x"):
            with self.subTest(path=path):
                self.erro("GET", path, None, 404, "Arquivo não encontrado.")
        self.erro("DELETE", "api/web-photos/xyz", None, 404, "Endereço não encontrado.")

    def test_cancelar_busca_que_nao_existe_responde_ok(self):
        self.assertEqual(self.app.ok("DELETE", "api/web-photos/fedcba9876543210"), {"ok": True})

    def test_cancelar_no_meio_nao_deixa_fotos_baixadas(self):
        jid = self.app.ok("POST", "api/web-photos", {"name": "Cafeteira"})["id"]
        self.assertEqual(self.app.ok("DELETE", f"api/web-photos/{jid}"), {"ok": True})
        time.sleep(1.0)  # a busca simulada pensa 0,4 s e para, porque foi cancelada
        self.assertEqual([n for n in os.listdir(self.app.path("data", "tmp")) if n.startswith(f"web-{jid}")], [])
        st, _, out = self.app.get(f"api/web-photos/{jid}")
        self.assertNotEqual((st, out.get("stage")), (200, "done"), "cancelada, o resultado não chega")


class SimuladaSemResposta(IaCase):
    """A IA simulada sem resposta de busca (sem INV_MOCK_SEARCH), ou com páginas sem foto boa."""

    @classmethod
    def setUpClass(cls):
        cls.site = FakeSite()
        cls.pasta = tempfile.mkdtemp(prefix="inventaria-busca-")
        cls.app = AppServer(mock_ai=True)
        sem_fotos = {"paginas": [{"url": cls.site.base + "semfoto.html"}, {"url": cls.site.base + "pequena.html"}],
                     "produto": {"nome": "Chaleira Exemplo K-1", "detalhes": "Chaleira elétrica de 1,7 L.", "categoria": "cozinha", "valor": "120"}}
        cls.sem_fotos = AppServer(mock_ai=True, env={"INV_MOCK_SEARCH": escrever_busca(cls.pasta, sem_fotos), "INV_WEB_ALLOW_LOCAL": "1"})

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()
        cls.sem_fotos.stop()
        cls.site.stop()
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def test_ia_que_nao_usou_a_busca_termina_em_erro_explicando(self):
        jid = self.app.ok("POST", "api/web-photos", {"name": "Cafeteira"})["id"]
        st, res = self.esperar_busca(jid)
        self.assertEqual((st, res["stage"], res["results"], res["product"]), (200, "error", [], None))
        self.assertTrue(res["msg"].startswith("A IA não usou a busca na web."))
        self.assertIn("Enable web search", res["msg"])
        self.assertEqual(self.uso()["recent"][0]["result"], "sem_busca")

    def test_paginas_sem_foto_boa_trazem_os_dados_do_produto(self):
        jid = self.sem_fotos.ok("POST", "api/web-photos", {"name": "Chaleira"})["id"]
        st, res = self.esperar_busca(jid, app=self.sem_fotos)
        self.assertEqual((res["stage"], res["results"]), ("error", []))
        self.assertIn("Não achei fotos desse produto", res["msg"])
        self.assertEqual(res["product"], {"name": "Chaleira Exemplo K-1", "details": "Chaleira elétrica de 1,7 L.", "cat": "cozinha", "value": 120})


class Desligada(IaCase):
    """Usar IA desligado: nada chama a IA, o servidor recusa com 409; o Falar some junto (recusa também)."""

    @classmethod
    def setUpClass(cls):
        cls.app = AppServer(mock_ai=True)
        cls.app.ok("PUT", "api/settings", {"ai": False})

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def test_ler_foto_recusa_antes_de_conferir_o_pedido(self):
        for body in ({"file": "sala-1.jpg", "mode": "single"}, {}, {"hint": "h" * 999}):
            with self.subTest(body=str(body)[:30]):
                self.erro("POST", "api/ai/identify", body, 409, DESLIGADA)

    def test_texto_falado_recusa(self):
        for body in ({"text": "sofá cinza"}, {}):
            with self.subTest(body=body):
                self.erro("POST", "api/ai/text", body, 409, DESLIGADA)

    def test_busca_na_internet_recusa(self):
        for body in ({"name": "Cafeteira"}, {}):
            with self.subTest(body=body):
                self.erro("POST", "api/web-photos", body, 409, DESLIGADA)

    def test_situacao_e_foto_de_busca_recusam_e_cancelar_continua(self):
        jid = "0123456789abcdef"
        self.erro("GET", f"api/web-photos/{jid}", None, 409, DESLIGADA)
        self.erro("GET", f"api/web-photos/{jid}/0", None, 409, DESLIGADA)
        self.assertEqual(self.app.ok("DELETE", f"api/web-photos/{jid}"), {"ok": True})

    def test_estado_e_uso_continuam_respondendo(self):
        self.assertTrue(self.app.ok("GET", "api/ai/status")["ready"], "a tela precisa saber se dá para ligar")
        self.assertEqual(self.app.get("api/ai/usage")[0], 200)

    def test_falar_recusa(self):
        self.assertTrue(self.app.ok("GET", "api/voice/status")["ready"], "o estado continua respondendo")
        self.erro("POST", "api/voice", None, 409, DESLIGADA, raw=PCM, headers=OCTET)
        st, _, out = self.app.request("GET", "api/rev")
        self.assertEqual(st, 200, "o áudio recusado não atrapalha o próximo pedido na mesma conexão")

    def test_recusas_nao_contam_no_uso(self):
        antes = self.uso()["today"]["calls"]
        self.app.post("api/ai/identify", {"file": "sala-1.jpg"})
        self.app.post("api/ai/text", {"text": "sofá"})
        self.app.post("api/web-photos", {"name": "Cafeteira"})
        self.assertEqual(self.uso()["today"]["calls"], antes)
        self.assertFalse(self.app.data()["settings"]["ai"])


class SemHomeAssistant(IaCase, ServerCase):
    """Fora do Home Assistant (sem SUPERVISOR_TOKEN) e sem a IA simulada."""

    def test_ler_foto_responde_503_sem_deixar_copia_em_media(self):
        self.erro("POST", "api/ai/identify", {"file": "sala-1.jpg"}, 503, SEM_HA)
        pasta = self.app.path("media", "inventario", "ia-temp")
        self.assertEqual(os.listdir(pasta) if os.path.isdir(pasta) else [], [])

    def test_texto_falado_responde_503(self):
        self.erro("POST", "api/ai/text", {"text": "sofá cinza"}, 503, SEM_HA)

    def test_falar_explica_o_que_falta(self):
        st = self.app.ok("GET", "api/voice/status?fresh=1")
        self.assertEqual((st["ready"], st["engines"], st["missing"]), (False, [], False))
        self.assertIn("Configurações > Assistentes de voz", st["reason"])
        self.erro("POST", "api/voice", None, 409, st["reason"], raw=PCM, headers=OCTET)

    def test_audio_curto_recusado_antes_de_procurar_a_fala(self):
        self.erro("POST", "api/voice", None, 422, "Não ouvi nada. Toque no microfone e fale.", raw=b"\x00" * 10, headers=OCTET)

    def test_sem_pasta_media_explica(self):
        app = self.fresh(env={"INV_MEDIA": "/proc/inventaria-sem-media"})
        st, _, out = app.post("api/ai/identify", {"file": "sala-1.jpg"})
        self.assertEqual((st, out["error"]), (500, "A pasta media não está disponível para o app."))


if __name__ == "__main__":
    unittest.main()
