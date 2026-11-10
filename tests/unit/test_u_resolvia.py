"""Tarefas no ResolvIA (1.47.0): só com Usar equipamentos ligado no ResolvIA (os equipamentos em
share/resolvia/integracao.json); as listas do Home Assistant que aceitam tarefa nova (e se aceitam prazo); a tarefa nova
entra na lista (todo.add_item) e o evento resolvia_comodo a liga ao item e ao cômodo; as tarefas abertas de cada item vêm
pela ligação do ResolvIA (o nome da tarefa como ele guarda) e pelas tarefas abertas da lista. Listas e tarefas inventadas."""
import json
import os
import tempfile
from unittest import mock

from _boot import UnitBase, server as S

LISTAS = [{"entity_id": "todo.casa", "state": "2", "attributes": {"friendly_name": "Casa", "supported_features": 1 | 16}},
          {"entity_id": "todo.mercado", "state": "0", "attributes": {"friendly_name": "Mercado", "supported_features": 1}},
          {"entity_id": "todo.so_leitura", "state": "0", "attributes": {"friendly_name": "Só leitura", "supported_features": 0}}]


class TarefasNoResolvia(UnitBase):
    def setUp(self):
        super().setUp()
        self.arq = os.path.join(tempfile.mkdtemp(prefix="inv-rv-"), "integracao.json")
        p = mock.patch.object(S, "RESOLVIA_ARQ", self.arq)
        p.start()
        self.addCleanup(p.stop)
        S._rv.update(mtime=None, info=None)
        self.it = next(i for i in self.store.data["items"] if i.get("room"))
        self.ha = self.fake_ha()
        self.ha.states += [dict(x) for x in LISTAS]

    def resolvia(self, equipamentos=True, tarefas=None, quando=None, **mais):
        with open(self.arq, "w", encoding="utf-8") as f:
            json.dump({"app": "ResolvIA", "nome": "ResolvIA", **({"equipamentos": {"lista": [], "tarefas": tarefas or {}}} if equipamentos else {}), **mais}, f)
        os.utime(self.arq, (quando or 1000, quando or 1000))

    def test_so_com_os_equipamentos_ligados_la(self):
        self.assertFalse(S.resolvia_on(), "sem o ResolvIA")
        self.resolvia(equipamentos=False)
        self.assertFalse(S.resolvia_on(), "o ResolvIA sem Usar equipamentos")
        self.assertApiError(409, S.resolvia_nova, {"item": self.it["id"], "lista": "todo.casa", "tarefa": "Trocar o filtro"}, msg_part="Usar equipamentos")
        self.resolvia(quando=2000)
        self.assertTrue(S.resolvia_on())

    def test_as_listas_que_aceitam_tarefa(self):
        # um ResolvIA de antes da 2.57.0 (sem "listas"): as do Home Assistant que aceitam tarefa nova
        self.assertEqual(S.resolvia_listas(), [{"id": "todo.casa", "nome": "Casa", "cor": None, "prazo": True}, {"id": "todo.mercado", "nome": "Mercado", "cor": None, "prazo": False}])
        self.resolvia(sem_prazo=["todo.casa"])
        self.assertFalse(S.resolvia_listas()[0]["prazo"], "datas só como informação na lista: sem prazo")
        self.resolvia(prazos=False, quando=2000)
        self.assertEqual([x["prazo"] for x in S.resolvia_listas()], [False, False], "Controlar prazos desligado lá: sem prazo")

    def test_1_48_as_listas_como_o_resolvia_mostra(self):
        # o ResolvIA 2.57.0 publica as listas dele: os nomes e as cores de lá, na ordem de lá, sem as desmarcadas
        self.resolvia(listas=[{"id": "todo.mercado", "nome": "Compras  da casa", "cor": "#4ED3A6", "prazo": False},
                              {"id": "todo.casa", "nome": "Casa", "cor": "vermelho", "prazo": True}, {"id": "light.sala"}, "x"])
        self.assertEqual(S.resolvia_listas(), [{"id": "todo.mercado", "nome": "Compras da casa", "cor": "#4ED3A6", "prazo": False},
                                               {"id": "todo.casa", "nome": "Casa", "cor": None, "prazo": True}])
        self.assertEqual(self.ha.calls("GET", "/core/api/states"), [], "sem perguntar ao Home Assistant")
        self.resolvia(prazos=False, quando=2000, listas=[{"id": "todo.casa", "nome": "Casa", "cor": "#FF5A4F", "prazo": True}])
        self.assertEqual(S.resolvia_listas(), [{"id": "todo.casa", "nome": "Casa", "cor": "#FF5A4F", "prazo": False}], "Controlar prazos desligado lá")

    def test_1_48_so_as_listas_do_resolvia_e_o_prazo_so_com_controlar_prazos(self):
        base = {"item": self.it["id"], "lista": "todo.casa", "tarefa": "Trocar o filtro"}
        self.resolvia(listas=[{"id": "todo.casa", "nome": "Minha casa", "cor": "#FF5A4F", "prazo": True}])
        self.assertApiError(400, S.resolvia_nova, {**base, "lista": "todo.mercado"}, msg_part="Escolha uma lista")
        self.assertEqual(S.resolvia_nova(base)["nome_lista"], "Minha casa")
        self.resolvia(prazos=False, quando=2000, listas=[{"id": "todo.casa", "nome": "Minha casa", "cor": "#FF5A4F", "prazo": False}])
        self.assertApiError(400, S.resolvia_nova, {**base, "prazo": "2026-11-20"}, msg_part="Controlar prazos")
        self.assertEqual(self.ha.todo_items["todo.casa"], [{"summary": "Trocar o filtro", "uid": "u1", "status": "needs_action"}])

    def test_cria_e_liga_ao_item(self):
        self.resolvia()
        r = S.resolvia_nova({"item": self.it["id"], "lista": "todo.casa", "tarefa": "  Trocar   o filtro ", "prazo": "2026-11-20"}, "Ana")
        self.assertEqual((r["tarefa"], r["nome_lista"], r["ligada"]), ("Trocar o filtro", "Casa", True))
        self.assertEqual(self.ha.todo_items["todo.casa"], [{"summary": "Trocar o filtro", "uid": "u1", "status": "needs_action", "due": "2026-11-20"}])
        self.assertEqual(self.ha.events, [("resolvia_comodo", {"entity_id": "todo.casa", "tarefa": "Trocar o filtro", "equipamento": self.it["id"],
                                                               "origem": "InventarIA", "comodo": self.it["room"]})])

    def test_erros(self):
        self.resolvia()
        base = {"item": self.it["id"], "lista": "todo.casa", "tarefa": "Trocar o filtro"}
        self.assertApiError(404, S.resolvia_nova, {**base, "item": "nada"})
        self.assertApiError(400, S.resolvia_nova, {**base, "tarefa": "  "}, msg_part="nome")
        self.assertApiError(400, S.resolvia_nova, {**base, "lista": "todo.so_leitura"}, msg_part="lista")
        self.assertApiError(400, S.resolvia_nova, {**base, "prazo": "amanhã"}, msg_part="Prazo")
        self.assertApiError(400, S.resolvia_nova, {**base, "lista": "todo.mercado", "prazo": "2026-11-20"}, msg_part="não aceita prazo")
        self.assertEqual(self.ha.todo_items, {}, "nada foi criado")

    def test_sem_o_evento_a_tarefa_fica_sem_a_ligacao(self):
        self.resolvia()
        self.ha.events_status = 500
        r = S.resolvia_nova({"item": self.it["id"], "lista": "todo.mercado", "tarefa": "Comprar pilhas"})
        self.assertEqual((r["ligada"], len(self.ha.todo_items["todo.mercado"])), (False, 1))

    def test_as_tarefas_abertas_do_item(self):
        iid = self.it["id"]
        self.ha.todo_items = {
            "todo.casa": [{"summary": "Trocar o Filtro", "uid": "a", "status": "needs_action", "due": "2026-11-20"},
                          {"summary": "Limpar a coifa", "uid": "b", "status": "needs_action"},
                          {"summary": "Revisão", "uid": "c", "status": "completed"},
                          {"summary": "Outra coisa", "uid": "d", "status": "needs_action"}],
            "todo.mercado": [{"summary": "Pilhas", "uid": "e", "status": "needs_action"}]}
        self.resolvia(tarefas={"todo.casa": {"trocar o filtro": iid, "limpar a coifa": [iid, "outro"], "revisao": iid, "outra coisa": "outro"},
                               "todo.mercado": {"pilhas": "outro"}, "sensor.x": {"a": iid}})
        self.assertEqual(S.resolvia_tarefas(iid), [
            {"lista": "todo.casa", "nome_lista": "Casa", "tarefa": "Trocar o Filtro", "prazo": "2026-11-20"},
            {"lista": "todo.casa", "nome_lista": "Casa", "tarefa": "Limpar a coifa", "prazo": ""}],
            "as abertas ligadas ao item, as com prazo primeiro; a concluída e as de outro item ficam fora")
        self.assertEqual(len(self.ha.calls("POST", "/core/api/services/todo/get_items")), 1, "só pergunta à lista que tem tarefa do item")
        # com as listas do ResolvIA: o nome de lá (uma lista desmarcada lá fica com o do Home Assistant)
        self.resolvia(quando=2000, listas=[{"id": "todo.casa", "nome": "Minha casa", "cor": "#FF5A4F", "prazo": True}],
                      tarefas={"todo.casa": {"trocar o filtro": iid}, "todo.mercado": {"pilhas": iid}})
        self.assertEqual({(t["lista"], t["nome_lista"]) for t in S.resolvia_tarefas(iid)}, {("todo.casa", "Minha casa"), ("todo.mercado", "Mercado")})

    def test_o_nome_como_o_resolvia_guarda(self):
        self.assertEqual(S.task_key("  Trocar   o FILTRO da Cozinha  "), "trocar o filtro da cozinha")
        self.assertEqual(S.task_key("Revisão do ar-condicionado"), "revisao do ar-condicionado")
