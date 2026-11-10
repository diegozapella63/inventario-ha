"""Ajustes das novidades (Mais > Configurações > Opções): ligar e desligar, conferir sozinho de tempos em tempos e o aviso
no celular ("Novidades em 3 itens. Toque para abrir.", que abre o app em Novidades)."""
import time
import unittest
from datetime import datetime, timedelta
from unittest import mock

from _boot import UnitBase, server


def ago(days=0.0, hours=0.0) -> str:
    return (datetime.now().astimezone() - timedelta(days=days, hours=hours)).isoformat(timespec="seconds")


class Ligar(UnitBase):
    def test_ligadas_de_inicio(self):
        self.assertTrue(server.news_enabled())
        server.need_news_on()  # não recusa

    def test_desligadas_recusam_com_o_caminho(self):
        self.store.settings["news"] = False
        with self.assertRaises(server.ApiError) as e:
            server.need_news_on()
        self.assertEqual(e.exception.status, 409)
        self.assertIn("Mais > Configurações > Opções", e.exception.msg)

    def test_ia_desligada_recusa_antes(self):
        self.store.settings["ai"] = False
        with self.assertRaises(server.ApiError) as e:
            server.need_news_on()
        self.assertIn("A IA está desligada", e.exception.msg)


class Intervalo(UnitBase):
    def test_de_inicio_nao_confere_sozinho(self):
        self.assertEqual(server.news_every(), 0)

    def test_so_os_intervalos_da_lista(self):
        for v, want in ((7, 7), (15, 15), (30, 30), (3, 0), ("7", 0), (True, 0), (None, 0)):
            self.store.settings["news_every"] = v
            self.assertEqual(server.news_every(), want, repr(v))


class Destino(UnitBase):
    def test_todos_ou_uma_pessoa(self):
        for v, want in (("todos", "todos"), ("person.ana", "person.ana"), ("", ""), ("persistent", ""), ("mobile_app_celular_da_ana", ""),
                        ("person.Ana", ""), ("person.a/../b", ""), ("light.sala", ""), (None, "")):
            self.store.settings["news_notify"] = v
            self.assertEqual(server.news_notify_target(), want, repr(v))

    def test_slug_como_o_home_assistant(self):
        self.assertEqual(server.ha_slug("Celular da Ana"), "celular_da_ana")
        self.assertEqual(server.ha_slug("Relógio  Zé!"), "relogio_ze")


class Pessoas(UnitBase):
    """O aviso vai para a pessoa: os celulares dela são os do app Home Assistant entre os rastreadores dela (como no
    ResolvIA e na CronologIA)."""

    def test_pessoas_e_celulares(self):
        self.fake_ha()
        self.assertEqual(server.news_people(), [
            {"id": "person.ana", "name": "Ana", "user_id": "u-ana", "phones": ["mobile_app_celular_da_ana"]},  # pelo nome do aparelho, não do rastreador
            {"id": "person.beto", "name": "Beto", "user_id": "u-beto", "phones": []},  # o roteador não é celular
            {"id": "person.carla", "name": "Carla", "user_id": "", "phones": ["mobile_app_tablet_da_sala"]},  # fora dos registros: pelo nome do rastreador
        ])

    def test_sem_os_registros_pelo_nome_do_rastreador(self):
        ha = self.fake_ha()
        ha.ws_fail = True
        ana = next(p for p in server.news_people() if p["id"] == "person.ana")
        self.assertEqual(ana["phones"], [], "device_tracker.pixel_ana → mobile_app_pixel_ana, que não existe")
        carla = next(p for p in server.news_people() if p["id"] == "person.carla")
        self.assertEqual(carla["phones"], ["mobile_app_tablet_da_sala"])

    def test_rastreadores_tortos(self):
        self.assertEqual(server.tracker_phones(None, {"mobile_app_x"}, None), [])
        self.assertEqual(server.tracker_phones(["device_tracker.x", "device_tracker.x"], {"mobile_app_x"}, None), ["mobile_app_x"], "sem repetir")
        self.assertEqual(server.tracker_phones(["device_tracker.x"], {"mobile_app_x"}, {"device_tracker.x": None}), [], "rastreador sem aparelho")

    def test_cache_de_um_minuto(self):
        ha = self.fake_ha()
        server.news_people()
        n = len(ha.calls("GET", "/core/api/states"))
        server.news_people()
        self.assertEqual(len(ha.calls("GET", "/core/api/states")), n)

    def test_sem_home_assistant_ninguem(self):
        self.assertEqual(server.news_people(), [])

    def test_celulares_de_quem_recebe(self):
        self.fake_ha()
        self.assertEqual(server.news_phones("todos"), ["mobile_app_celular_da_ana", "mobile_app_tablet_da_sala"],
                         "todos: os celulares de todas as pessoas (o celular de ninguém fica de fora)")
        self.assertEqual(server.news_phones("person.ana"), ["mobile_app_celular_da_ana"])
        with self.assertRaises(server.ApiError) as e:
            server.news_phones("person.beto")
        self.assertEqual(e.exception.msg, "Sem celular ligado a Beto no Home Assistant (Configurações > Pessoas).")
        with self.assertRaises(server.ApiError) as e:
            server.news_phones("person.zeca")
        self.assertIn("não está mais no Home Assistant", e.exception.msg)


class NovasEntradas(UnitBase):
    A = {"titulo": "Atualização 2.1", "fonte": "https://fab.exemplo/a"}
    B = {"titulo": "Modelo 2027", "fonte": "https://fab.exemplo/b"}

    def test_sem_busca_anterior_tudo_e_novo(self):
        self.assertEqual(server.news_new_entries(None, {"novidades": [self.A, self.B]}), [self.A, self.B])

    def test_a_mesma_fonte_nao_e_nova(self):
        self.assertEqual(server.news_new_entries({"novidades": [self.A]}, {"novidades": [self.A, self.B]}), [self.B])

    def test_o_mesmo_titulo_com_outra_fonte_nao_e_novo(self):
        antes = {"novidades": [{"titulo": "ATUALIZAÇÃO 2.1", "fonte": "https://outro.exemplo/x"}]}
        self.assertEqual(server.news_new_entries(antes, {"novidades": [self.A]}), [])

    def test_nada_achado(self):
        self.assertEqual(server.news_new_entries({"novidades": [self.A]}, {"novidades": []}), [])


class Aviso(UnitBase):
    def test_texto(self):
        with mock.patch.object(server.socket, "gethostname", return_value="a1b2c3d4-inventario"):
            n = server.news_notice(3)
            self.assertEqual(n["title"], "InventarIA")
            self.assertEqual(n["message"], "Novidades em 3 itens. Toque para abrir.")
            self.assertEqual(n["link"], "/app/a1b2c3d4_inventario/novidades", "abre o app em Novidades, no Home Assistant")
            self.assertEqual(server.news_notice(1)["message"], "Novidades em 1 item. Toque para abrir.")
            self.assertEqual(server.news_notice(2, test=True)["title"], "InventarIA (teste)")

    def test_fora_do_home_assistant_sem_link(self):
        with mock.patch.object(server.socket, "gethostname", return_value="meu-computador"):
            self.assertIsNone(server.news_notice(2)["link"])

    def test_para_a_pessoa(self):
        ha = self.fake_ha()
        with mock.patch.object(server.socket, "gethostname", return_value="local-inventario"):
            self.assertEqual(server.send_news_notice(3, "person.ana"), 1)
        c = ha.calls("POST", "/core/api/services/notify/")
        self.assertEqual([x["path"] for x in c], ["/core/api/services/notify/mobile_app_celular_da_ana"], "no celular da Ana")
        b = c[0]["body"]
        self.assertEqual((b["title"], b["message"]), ("InventarIA", "Novidades em 3 itens. Toque para abrir."))
        self.assertEqual(b["data"]["url"], "/app/local_inventario/novidades", "no iPhone, tocar abre o app em Novidades")
        self.assertEqual(b["data"]["clickAction"], "/app/local_inventario/novidades", "no Android também")
        self.assertEqual(b["data"]["tag"], "inventaria-novidades", "um aviso novo troca o anterior, não empilha")

    def test_para_todos(self):
        ha = self.fake_ha()
        self.assertEqual(server.send_news_notice(2, "todos"), 2)
        self.assertEqual(sorted(x["path"].rsplit("/", 1)[1] for x in ha.calls("POST", "/core/api/services/notify/")),
                         ["mobile_app_celular_da_ana", "mobile_app_tablet_da_sala"])

    def test_nenhum_celular_recebe_da_erro(self):
        ha = self.fake_ha()
        ha.notify_status = 500
        with self.assertRaises(server.ApiError):
            server.send_news_notice(2, "todos")

    def test_o_escolhido_nas_opcoes(self):
        self.fake_ha()
        self.store.settings["news_notify"] = "person.carla"
        self.assertEqual(server.send_news_notice(2), 1)

    def test_sem_destino_recusa(self):
        self.fake_ha()
        for who in ("", "persistent", "mobile_app_celular_da_ana"):
            with self.assertRaises(server.ApiError) as e:
                server.send_news_notice(2, who)
            self.assertEqual((e.exception.status, e.exception.msg), (400, "Escolha quem avisar."))


class Sozinho(UnitBase):
    def setUp(self):
        super().setUp()
        self.store.settings["news_every"] = 7

    def ultima(self, at, tentativa=None):
        d = server.news_read()
        d["ultima"] = {"at": at, "conferidos": 1} if at else None
        if tentativa:
            d["auto_tentativa"] = tentativa
        server.write_json_atomic(server.NEWS_FILE, d)

    def test_nunca_conferido_confere(self):
        self.assertTrue(server.news_auto_due(time.time()))

    def test_desligado_nao_confere(self):
        self.store.settings["news_every"] = 0
        self.assertFalse(server.news_auto_due(time.time()))

    def test_novidades_ou_ia_desligadas_nao_conferem(self):
        for key in ("news", "ai"):
            with self.subTest(key=key):
                self.store.settings[key] = False
                self.assertFalse(server.news_auto_due(time.time()))
                self.store.settings[key] = True

    def test_conferido_ha_pouco_espera(self):
        self.ultima(ago(days=3))
        self.assertFalse(server.news_auto_due(time.time()))

    def test_passou_o_intervalo_confere(self):
        self.ultima(ago(days=7, hours=0.5))
        self.assertTrue(server.news_auto_due(time.time()))
        self.ultima(ago(days=6, hours=23.5))
        self.assertTrue(server.news_auto_due(time.time()), "com uma hora de folga, para não escorregar a cada semana")

    def test_depois_de_uma_tentativa_espera_6_horas(self):
        self.ultima(ago(days=10), tentativa=ago(hours=2))
        self.assertFalse(server.news_auto_due(time.time()))
        self.ultima(ago(days=10), tentativa=ago(hours=7))
        self.assertTrue(server.news_auto_due(time.time()))


if __name__ == "__main__":
    unittest.main()
