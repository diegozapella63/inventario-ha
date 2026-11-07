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
    def test_celular_ou_aviso_do_home_assistant(self):
        for v, want in (("persistent", "persistent"), ("mobile_app_celular_da_ana", "mobile_app_celular_da_ana"), ("", ""),
                        ("notify.mobile_app_x", ""), ("mobile_app_X", ""), ("mobile_app_a/../b", ""), (None, "")):
            self.store.settings["news_notify"] = v
            self.assertEqual(server.news_notify_target(), want, repr(v))

    def test_nome_do_celular(self):
        self.assertEqual(server.phone_name("mobile_app_celular_da_ana"), "Celular da Ana")
        self.assertEqual(server.phone_name("mobile_app_tablet_da_sala"), "Tablet da Sala")
        self.assertEqual(server.phone_name("mobile_app_de_teste"), "De Teste", "a primeira palavra sempre maiúscula")


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

    def test_no_celular(self):
        ha = self.fake_ha()
        with mock.patch.object(server.socket, "gethostname", return_value="local-inventario"):
            server.send_news_notice(3, "mobile_app_celular_da_ana")
        c = ha.calls("POST", "/core/api/services/notify/")
        self.assertEqual([x["path"] for x in c], ["/core/api/services/notify/mobile_app_celular_da_ana"])
        b = c[0]["body"]
        self.assertEqual((b["title"], b["message"]), ("InventarIA", "Novidades em 3 itens. Toque para abrir."))
        self.assertEqual(b["data"]["url"], "/app/local_inventario/novidades", "no iPhone, tocar abre o app em Novidades")
        self.assertEqual(b["data"]["clickAction"], "/app/local_inventario/novidades", "no Android também")
        self.assertEqual(b["data"]["tag"], "inventaria-novidades", "um aviso novo troca o anterior, não empilha")

    def test_no_home_assistant(self):
        ha = self.fake_ha()
        with mock.patch.object(server.socket, "gethostname", return_value="local-inventario"):
            server.send_news_notice(2, "persistent")
        c = ha.calls("POST", "/core/api/services/persistent_notification/create")
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]["body"]["message"], "Novidades em 2 itens. [Abrir as novidades](/app/local_inventario/novidades)")
        self.assertEqual(c[0]["body"]["notification_id"], "inventaria_novidades")

    def test_sem_destino_recusa(self):
        self.fake_ha()
        with self.assertRaises(server.ApiError) as e:
            server.send_news_notice(2, "")
        self.assertEqual(e.exception.status, 400)

    def test_celulares_do_home_assistant(self):
        self.fake_ha()
        self.assertEqual(server.notify_targets(), [{"id": "mobile_app_celular_da_ana", "name": "Celular da Ana"},
                                                   {"id": "mobile_app_tablet_da_sala", "name": "Tablet da Sala"}],
                         "só os celulares (notify.mobile_app_*), sem notify.notify nem a de luz")

    def test_sem_home_assistant_nenhum_celular(self):
        self.assertEqual(server.notify_targets(), [])


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
