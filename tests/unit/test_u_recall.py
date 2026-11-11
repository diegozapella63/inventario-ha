"""binary_sensor.inventaria_recall (1.55.0): ligado quando as Novidades acharam um recall de um item (recall_state,
publish_recall_sensor, remove_recall_sensor, publish_sensors e remove_sensors), com o Home Assistant simulado."""
import unittest
from unittest import mock

from _boot import UnitBase, helpers, server as S


def novidade(tipo, titulo, boato=False):
    return {"tipo": tipo, "titulo": titulo, "resumo": "", "data": "2026-10-20", "fonte": "https://www.exemplo.com.br/aviso", "site": "exemplo.com.br", "boato": boato}


class Recall(UnitBase):
    def setUp(self):
        super().setUp()
        self.ha = self.fake_ha()
        self.store.settings.update(ha_sensors=True)

    def guarda(self, iid, *novidades):
        S.news_save_result(iid, {"produto": "", "novidades": list(novidades)})

    def posts(self):
        return self.ha.calls("POST", "/core/api/states/" + S.RECALL_SENSOR)

    def test_sem_recall_fica_desligado(self):
        self.guarda("sal-007", novidade("atualizacao", "Atualização do sistema"))
        S.publish_recall_sensor()
        st = self.ha.state(S.RECALL_SENSOR)
        self.assertEqual((st["state"], st["attributes"]["quantidade"], st["attributes"]["device_class"]), ("off", 0, "problem"))
        self.assertEqual(st["attributes"]["icon"], "mdi:shield-check-outline")

    def test_recall_liga_com_o_item_e_o_comodo_sem_boato(self):
        self.guarda("sal-007", novidade("recall", "Recall da fonte de energia"), novidade("recall", "Dizem que vai ter recall", boato=True))
        self.guarda("sal-009", novidade("lancamento", "Modelo novo"))
        S.publish_recall_sensor()
        st = self.ha.state(S.RECALL_SENSOR)
        self.assertEqual(st["state"], "on")
        self.assertEqual(st["attributes"]["itens"], [{"item": "Smart TV 55 polegadas", "comodo": "Sala de estar", "titulo": "Recall da fonte de energia",
                                                      "data": "2026-10-20", "fonte": "https://www.exemplo.com.br/aviso"}])
        self.assertEqual((st["attributes"]["quantidade"], st["attributes"]["friendly_name"]), (1, "InventarIA: recall"))

    def test_so_manda_de_novo_quando_muda_ou_depois_de_15_minutos(self):
        S.publish_recall_sensor()
        S.publish_recall_sensor()
        self.assertEqual(len(self.posts()), 1)
        self.guarda("sal-007", novidade("recall", "Recall da fonte"))
        S.publish_recall_sensor()
        self.assertEqual(len(self.posts()), 2)
        S._recall_sensor["at"] -= 901
        S.publish_recall_sensor()
        self.assertEqual(len(self.posts()), 3, "o Home Assistant reiniciou: volta em até 15 minutos")

    def test_um_item_apagado_ou_um_bem_escondido_sai(self):
        self.guarda("sal-007", novidade("recall", "Recall da fonte"))
        self.store.data["items"] = [i for i in self.store.data["items"] if i["id"] != "sal-007"]
        self.assertEqual(S.recall_state()["state"], "off")

    def test_desligados_nao_publicam(self):
        for over in ({"ha_sensors": False}, {"ai": False}, {"news": False}):
            with mock.patch.dict(self.store.settings, over):
                S.publish_recall_sensor()
        with mock.patch.object(S, "AI_MOCK", True):
            S.publish_recall_sensor()
        self.assertEqual(self.posts(), [])

    def test_home_assistant_fora_do_ar_tenta_de_novo(self):
        with mock.patch.object(S, "HA_API", f"http://127.0.0.1:{helpers.free_port()}/core/api"):
            S.publish_recall_sensor()
        self.assertIsNone(S._recall_sensor["sig"])
        S.publish_recall_sensor()
        self.assertEqual(len(self.posts()), 1)
        S._recall_sensor["sig"] = "antes"
        with mock.patch.object(S, "HA_API", f"http://127.0.0.1:{helpers.free_port()}/core/api"):
            S.publish_recall_sensor(force=True)
        self.assertIsNone(S._recall_sensor["sig"])

    def test_ligar_e_desligar_os_dois(self):
        S.publish_sensors()
        self.assertIsNotNone(self.ha.state(S.RECALL_SENSOR))
        self.assertIsNotNone(self.ha.state(S.USAGE_SENSOR))
        self.store.settings["news"] = False
        S.publish_sensors()
        self.assertIsNone(self.ha.state(S.RECALL_SENSOR), "Novidades desligadas: o do recall sai")
        self.assertIsNotNone(self.ha.state(S.USAGE_SENSOR))
        S.remove_sensors()
        self.assertEqual((self.ha.state(S.RECALL_SENSOR), self.ha.state(S.USAGE_SENSOR)), (None, None))
        self.assertIsNone(S._recall_sensor["sig"])

    def test_remover_sem_home_assistant_nao_tenta(self):
        with mock.patch.object(S, "SUPERVISOR_TOKEN", None):
            S.remove_recall_sensor()
        self.assertEqual(self.ha.calls("DELETE"), [])


if __name__ == "__main__":
    unittest.main()
