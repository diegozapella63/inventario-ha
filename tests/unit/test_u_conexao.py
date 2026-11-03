"""Ligação com os outros apps (ResolvIA e GerencIA), sem servidor: a chave (Conexao.chave), o endereço (endereco),
o arquivo em share/inventario (publicar), a autorização (autorizado) e o que /api/integracao/comodos e /api/integracao/itens
respondem (r_integracao_comodos e r_integracao_itens, com um objeto que faz o papel da requisição)."""
import json
import os
import shutil
import socket
import stat
import time
import unittest
from datetime import datetime
from http.client import HTTPMessage
from unittest import mock

from _boot import UnitBase, server as S

AGORA = "2026-11-15T10:00:00-03:00"


class Resposta:
    """Faz o papel do Handler nas funções r_*: guarda o que seria enviado."""

    def __init__(self):
        self.enviado = []

    def send_json(self, obj, status=200):
        self.enviado.append((status, json.loads(json.dumps(obj))))  # como sairia pela rede


class Chave(UnitBase):
    def test_chave_do_arquivo_e_reaproveitada_sem_a_quebra_de_linha(self):
        guardada = "k" * 40
        with open(os.path.join(S.DATA_DIR, "integracao.key"), "w", encoding="utf-8") as f:
            f.write(guardada + "\n")
        self.assertEqual(S.Conexao().chave(), guardada)
        with open(os.path.join(S.DATA_DIR, "integracao.key"), encoding="utf-8") as f:
            self.assertEqual(f.read(), guardada + "\n", "o arquivo de uma chave boa não é regravado")

    def test_chave_de_32_caracteres_e_aceita(self):
        guardada = "a1" * 16
        with open(os.path.join(S.DATA_DIR, "integracao.key"), "w", encoding="utf-8") as f:
            f.write(guardada)
        self.assertEqual(S.Conexao().chave(), guardada)

    def test_chave_curta_no_arquivo_e_regravada_com_a_nova(self):
        arq = os.path.join(S.DATA_DIR, "integracao.key")
        with open(arq, "w", encoding="utf-8") as f:
            f.write("curta")
        nova = S.Conexao().chave()
        with open(arq, encoding="utf-8") as f:
            self.assertEqual(f.read(), nova, "o app reiniciado lê a chave nova, não a curta")
        self.assertEqual(stat.S_IMODE(os.stat(arq).st_mode), 0o600)

    def test_chave_cria_a_pasta_de_dados_que_falta(self):
        pasta = os.path.join(S.DATA_DIR, "nova", "dados")
        with mock.patch.object(S, "DATA_DIR", pasta):
            c = S.Conexao()
            k = c.chave()
        self.assertTrue(os.path.isfile(os.path.join(pasta, "integracao.key")))
        self.assertEqual(c.arq_chave, os.path.join(pasta, "integracao.key"))
        self.assertGreaterEqual(len(k), 32)

    def test_chave_fica_na_memoria_do_app_rodando(self):
        c = S.Conexao()
        k = c.chave()
        os.unlink(c.arq_chave)
        self.assertEqual(c.chave(), k, "apagar o arquivo não troca a chave que os outros apps já leram")
        self.assertFalse(os.path.exists(c.arq_chave), "nem regrava o arquivo a cada chamada")

    def test_cada_instalacao_tem_a_sua_chave(self):
        k1 = S.Conexao().chave()
        with mock.patch.object(S, "DATA_DIR", os.path.join(S.DATA_DIR, "outra-casa")):
            k2 = S.Conexao().chave()
        self.assertNotEqual(k1, k2)

    def test_chave_so_tem_caracteres_seguros_para_cabecalho(self):
        k = S.Conexao().chave()
        self.assertRegex(k, r"^[A-Za-z0-9_-]{43,}$", "vai num cabeçalho Authorization sem precisar de escape")


class Endereco(UnitBase):
    def test_sem_url_interna_usa_o_nome_da_maquina_e_o_ip(self):
        with mock.patch.dict(os.environ), mock.patch.object(S.socket, "gethostname", return_value="inventaria-teste"), \
                mock.patch.object(S.socket, "gethostbyname", return_value="172.30.33.5") as resolve:
            os.environ.pop("INV_URL_INTERNA", None)
            self.assertEqual(S.Conexao().endereco(), (f"http://inventaria-teste:{S.PORT}", "172.30.33.5"))
        resolve.assert_called_once_with("inventaria-teste")

    def test_nome_que_nao_resolve_fica_sem_ip(self):
        with mock.patch.dict(os.environ), mock.patch.object(S.socket, "gethostname", return_value="inventaria-teste"), \
                mock.patch.object(S.socket, "gethostbyname", side_effect=socket.gaierror("sem nome")):
            os.environ.pop("INV_URL_INTERNA", None)
            self.assertEqual(S.Conexao().endereco(), (f"http://inventaria-teste:{S.PORT}", None))

    def test_url_interna_vazia_e_ignorada(self):
        with mock.patch.dict(os.environ, {"INV_URL_INTERNA": ""}), mock.patch.object(S.socket, "gethostname", return_value="maquina"), \
                mock.patch.object(S.socket, "gethostbyname", return_value="172.30.33.9"):
            self.assertEqual(S.Conexao().endereco(), (f"http://maquina:{S.PORT}", "172.30.33.9"))

    def test_url_interna_nao_procura_o_ip(self):
        with mock.patch.dict(os.environ, {"INV_URL_INTERNA": "http://inventaria.local:8099//"}), \
                mock.patch.object(S.socket, "gethostbyname") as resolve:
            self.assertEqual(S.Conexao().endereco(), ("http://inventaria.local:8099", None))
        resolve.assert_not_called()


class Publicar(UnitBase):
    def ler(self, c):
        with open(c.arq_share, encoding="utf-8") as f:
            return json.load(f)

    def test_grava_url_e_ip_url_com_a_porta(self):
        c = S.Conexao()
        with mock.patch.object(c, "endereco", return_value=("http://inventaria-teste:8099", "172.30.33.5")):
            c.publicar()
        info = self.ler(c)
        self.assertEqual((info["url"], info["ip_url"]), ("http://inventaria-teste:8099", f"http://172.30.33.5:{S.PORT}"))
        self.assertEqual(c.arq_share, os.path.join(S.SHARE_DIR, "integracao.json"))

    def test_sem_ip_grava_ip_url_nulo(self):
        c = S.Conexao()
        with mock.patch.dict(os.environ, {"INV_URL_INTERNA": "http://inventaria.local:8099"}):
            c.publicar()
        info = self.ler(c)
        self.assertEqual(info["url"], "http://inventaria.local:8099")
        self.assertIsNone(info["ip_url"])

    def test_grava_a_hora_da_gravacao(self):
        c = S.Conexao()
        c.publicar()
        quando = datetime.fromisoformat(self.ler(c)["gravado_em"])
        self.assertLess(abs((datetime.now() - quando).total_seconds()), 120, "um arquivo velho quer dizer que o app parou")

    def test_substitui_o_arquivo_anterior(self):
        c = S.Conexao()
        with open(c.arq_share, "w", encoding="utf-8") as f:
            json.dump({"app": "InventarIA", "chave": "velha", "url": "http://antigo:1"}, f)
        c.publicar()
        info = self.ler(c)
        self.assertEqual(info["chave"], c.chave())
        self.assertNotEqual(info["url"], "http://antigo:1")
        self.assertEqual(stat.S_IMODE(os.stat(c.arq_share).st_mode), 0o600)

    def test_cria_a_pasta_share_que_falta(self):
        shutil.rmtree(S.SHARE_DIR)
        c = S.Conexao()
        c.publicar()
        self.assertEqual(self.ler(c)["chave"], c.chave())

    def test_falha_ao_gravar_fica_no_registro(self):
        c = S.Conexao()
        c.arq_share = os.path.join(S.SHARE_DIR, "nao-existe", "integracao.json")
        with self.assertLogs("inventario", "WARNING") as cm:
            c.publicar()
        self.assertIn("não consegui gravar", cm.output[0])
        self.assertFalse(os.path.exists(os.path.join(S.SHARE_DIR, "integracao.json")), "nada pela metade em outro lugar")

    def test_a_chave_do_arquivo_e_a_que_abre_a_integracao(self):
        c = S.Conexao()
        c.publicar()
        chave = self.ler(c)["chave"]
        outra = S.Conexao()  # o app reiniciado
        self.assertTrue(outra.autorizado({"Authorization": f"Bearer {chave}"}))


class Autorizacao(UnitBase):
    def setUp(self):
        super().setUp()
        self.c = S.Conexao()
        self.k = self.c.chave()

    def test_espacos_em_volta_da_chave_sao_ignorados(self):
        self.assertTrue(self.c.autorizado({"Authorization": f"Bearer   {self.k}  "}))

    def test_bearer_vazio_e_recusado(self):
        for h in ("Bearer ", "Bearer    ", "Bearer"):
            with self.subTest(h=h):
                self.assertFalse(self.c.autorizado({"Authorization": h}))

    def test_chave_com_acentos_e_recusada_sem_erro(self):
        self.assertFalse(self.c.autorizado({"Authorization": "Bearer chave-com-ção-e-ñ"}))

    def test_cabecalhos_da_requisicao_sem_diferenca_de_maiusculas(self):
        m = HTTPMessage()  # o que o servidor recebe em self.headers
        m["authorization"] = f"Bearer {self.k}"
        m["x-app"] = "GerencIA"
        self.assertTrue(self.c.autorizado(m))
        self.assertEqual(self.c.ultimo["app"], "GerencIA")

    def test_sem_x_app_registra_outro_app(self):
        self.assertTrue(self.c.autorizado({"Authorization": f"Bearer {self.k}"}))
        self.assertEqual(self.c.ultimo["app"], "outro app")

    def test_nome_do_app_longo_e_cortado(self):
        self.assertTrue(self.c.autorizado({"Authorization": f"Bearer {self.k}", "X-App": "R" * 100}))
        self.assertEqual(self.c.ultimo["app"], "R" * 40)

    def test_ultimo_acesso_tem_a_hora(self):
        self.c.autorizado({"Authorization": f"Bearer {self.k}", "X-App": "ResolvIA"})
        quando = datetime.fromisoformat(self.c.ultimo["em"])
        self.assertIsNotNone(quando.tzinfo, "com fuso, como o resto do app")
        self.assertLess(abs(time.time() - quando.timestamp()), 120)

    def test_pedido_recusado_nao_muda_o_ultimo_acesso(self):
        self.c.autorizado({"Authorization": f"Bearer {self.k}", "X-App": "ResolvIA"})
        antes = dict(self.c.ultimo)
        self.assertFalse(self.c.autorizado({"Authorization": "Bearer errada", "X-App": "Invasor"}))
        self.assertEqual(self.c.ultimo, antes)

    def test_nenhum_acesso_ainda(self):
        self.assertFalse(self.c.autorizado({"X-App": "ResolvIA"}))
        self.assertIsNone(self.c.ultimo)


class IntegracaoComodos(UnitBase):
    def comodos(self):
        h = Resposta()
        S.r_integracao_comodos(h, {})
        (status, obj), = h.enviado
        self.assertEqual(status, 200)
        return obj

    def test_cada_comodo_tem_id_nome_codigo_e_itens(self):
        out = self.comodos()
        self.assertEqual(out["versao"], S.VERSION)
        self.assertEqual([set(c) for c in out["comodos"]], [{"id", "nome", "codigo", "itens"}] * 6)
        self.assertEqual(out["comodos"][1], {"id": "cozinha", "nome": "Cozinha", "codigo": "COZ", "itens": 7})

    def test_conta_os_itens_de_cada_comodo(self):
        conta = {c["id"]: c["itens"] for c in self.comodos()["comodos"]}
        self.assertEqual(conta, {"sala": 12, "cozinha": 7, "quarto": 6, "escritorio": 5, "lavanderia": 5, "varanda": 3})

    def test_na_ordem_de_organizar(self):
        self.store.reorder_rooms(["varanda", "cozinha", "sala", "quarto", "escritorio", "lavanderia"])
        self.assertEqual([c["id"] for c in self.comodos()["comodos"]], ["varanda", "cozinha", "sala", "quarto", "escritorio", "lavanderia"])

    def test_comodo_novo_aparece_com_zero_itens(self):
        r = self.store.create_room({"name": "Garagem", "code": "GAR"})
        ultimo = self.comodos()["comodos"][-1]
        self.assertEqual(ultimo, {"id": r["id"], "nome": "Garagem", "codigo": "GAR", "itens": 0})

    def test_comodo_sem_nome_usa_o_id_e_sem_codigo_fica_vazio(self):
        self.store.data["rooms"].append({"id": "sotao", "order": 99})
        self.assertEqual(self.comodos()["comodos"][-1], {"id": "sotao", "nome": "sotao", "codigo": "", "itens": 0})

    def test_item_excluido_sai_da_contagem(self):
        self.store.delete_item("var-001")
        self.assertEqual(next(c for c in self.comodos()["comodos"] if c["id"] == "varanda")["itens"], 2)

    def test_item_movido_conta_no_comodo_novo(self):
        self.store.update_item("var-002", {"room": "lavanderia"}, None)
        conta = {c["id"]: c["itens"] for c in self.comodos()["comodos"]}
        self.assertEqual((conta["varanda"], conta["lavanderia"]), (2, 6))


class IntegracaoItens(UnitBase):
    def resposta(self):
        h = Resposta()
        S.r_integracao_itens(h, {})
        (status, obj), = h.enviado
        self.assertEqual(status, 200)
        return obj

    def itens(self):
        return {i["id"]: i for i in self.resposta()["itens"]}

    def test_cada_item_tem_so_os_campos_combinados(self):
        out = self.resposta()
        self.assertEqual(out["versao"], S.VERSION)
        self.assertEqual(len(out["itens"]), 38)
        for it in out["itens"]:
            self.assertEqual(set(it), {"id", "nome", "comodo", "zona", "categoria", "valor", "valor_em"}, "nada de fotos, detalhes ou observações")

    def test_valores_do_item(self):
        geladeira = self.itens()["coz-004"]
        self.assertEqual(geladeira, {"id": "coz-004", "nome": "Geladeira frost free inox", "comodo": "cozinha", "zona": "Geladeira",
                                     "categoria": "cozinha", "valor": 2600.0, "valor_em": "2026-10-06"})
        self.assertIsInstance(geladeira["valor"], float)

    def test_ordem_por_comodo_e_depois_por_nome(self):
        out = self.resposta()["itens"]
        ordem = {r["id"]: r["order"] for r in self.store.data["rooms"]}
        chaves = [(ordem[i["comodo"]], i["nome"].lower()) for i in out]
        self.assertEqual(chaves, sorted(chaves))
        self.assertEqual(out[0]["comodo"], "sala")
        self.assertEqual(out[-1]["comodo"], "varanda")

    def test_ordem_do_nome_sem_diferenca_de_maiusculas(self):
        self.store.data["items"] += [{"id": "v-b", "room": "varanda", "name": "banco"}, {"id": "v-a", "room": "varanda", "name": "Alpendre"}]
        nomes = [i["nome"] for i in self.resposta()["itens"] if i["comodo"] == "varanda"]
        self.assertEqual(nomes[:2], ["Alpendre", "banco"])

    def test_item_sem_valor_vai_com_zero(self):
        self.store.data["items"] += [{"id": "x-1", "room": "sala", "name": "Sem valor"}, {"id": "x-2", "room": "sala", "name": "Nulo", "value": None},
                                     {"id": "x-3", "room": "sala", "name": "Zero", "value": 0}]
        it = self.itens()
        self.assertEqual([it[k]["valor"] for k in ("x-1", "x-2", "x-3")], [0.0, 0.0, 0.0])

    def test_valor_com_centavos_arredondado(self):
        self.store.update_item("sal-002", {"value": "1.234,567"}, None)
        self.assertEqual(self.itens()["sal-002"]["valor"], 1234.57)

    def test_valor_em_e_a_data_do_valor_novo(self):
        with mock.patch.object(S, "now_iso", return_value=AGORA):
            self.store.update_item("sal-001", {"value": 1500}, None)
        self.assertEqual(self.itens()["sal-001"]["valor_em"], "2026-11-15")

    def test_valor_igual_nao_marca_data_do_valor(self):
        with mock.patch.object(S, "now_iso", return_value=AGORA):
            self.store.update_item("coz-001", {"value": 650, "_base": self.item("coz-001")["updatedAt"]}, None)
        self.assertNotIn("valueAt", self.item("coz-001"))

    def test_item_novo_tem_a_data_da_criacao(self):
        with mock.patch.object(S, "now_iso", return_value=AGORA):
            novo, = self.store.create_items([{"room": "sala", "name": "Abajur", "value": 120}], None)
        self.assertEqual(self.itens()[novo["id"]]["valor_em"], "2026-11-15")

    def test_valor_em_nao_muda_quando_so_o_nome_muda(self):
        antes = self.itens()["sal-001"]["valor_em"]
        with mock.patch.object(S, "now_iso", return_value=AGORA):
            self.store.update_item("sal-001", {"name": "Sofá de 3 lugares azul", "checked": True}, None)
        self.assertEqual(self.itens()["sal-001"]["valor_em"], antes, "o valor não mudou: a data do valor também não")

    def test_valor_em_usa_a_criacao_sem_atualizacao(self):
        self.store.data["items"].append({"id": "x-1", "room": "sala", "name": "Antigo", "value": 10, "createdAt": "2025-03-04T08:00:00-03:00"})
        self.assertEqual(self.itens()["x-1"]["valor_em"], "2025-03-04")

    def test_valor_em_vazio_sem_nenhuma_data(self):
        self.store.data["items"].append({"id": "x-1", "room": "sala", "name": "Sem data", "value": 10})
        self.assertEqual(self.itens()["x-1"]["valor_em"], "")

    def test_categoria_vazia_vai_como_outros(self):
        self.store.data["items"] += [{"id": "x-1", "room": "sala", "name": "A"}, {"id": "x-2", "room": "sala", "name": "B", "cat": ""}]
        it = self.itens()
        self.assertEqual((it["x-1"]["categoria"], it["x-2"]["categoria"]), ("outros", "outros"))

    def test_categorias_padrao_com_os_nomes(self):
        self.assertEqual(self.resposta()["categorias"], S.CATS)

    def test_categorias_com_os_nomes_da_casa(self):
        nova = self.store.create_cat({"name": "Ferramentas"})
        self.store.update_cat("moveis", {"name": "Mobília"})
        self.store.update_item("lav-005", {"cat": nova["id"]}, None)
        out = self.resposta()
        self.assertEqual(out["categorias"][nova["id"]], "Ferramentas")
        self.assertEqual(out["categorias"]["moveis"], "Mobília")
        self.assertEqual(next(i for i in out["itens"] if i["id"] == "lav-005")["categoria"], nova["id"])

    def test_categoria_excluida_some_e_os_itens_vao_para_outros(self):
        self.store.delete_cat("plantas")
        out = self.resposta()
        self.assertNotIn("plantas", out["categorias"])
        self.assertNotIn("plantas", {i["categoria"] for i in out["itens"]})

    def test_no_maximo_2000_itens(self):
        self.store.data["items"] += [{"id": f"x-{n:04d}", "room": "varanda", "name": f"Caixa {n:04d}", "value": 1} for n in range(2100)]
        out = self.resposta()["itens"]
        self.assertEqual(len(out), 2000)
        self.assertEqual(sum(1 for i in out if i["comodo"] != "varanda"), 35, "os primeiros cômodos vêm inteiros; o corte é no fim")

    def test_item_sem_id_fica_de_fora(self):
        self.store.data["items"] += [{"room": "sala", "name": "Sem id"}, {"id": "", "room": "sala", "name": "Id vazio"}]
        nomes = {i["nome"] for i in self.resposta()["itens"]}
        self.assertFalse({"Sem id", "Id vazio"} & nomes)

    def test_item_de_comodo_que_nao_existe_vai_para_o_fim(self):
        self.store.data["items"].append({"id": "x-1", "room": "garagem", "name": "Aaa primeiro no nome"})
        out = self.resposta()["itens"]
        self.assertEqual((out[-1]["id"], out[-1]["comodo"]), ("x-1", "garagem"))

    def test_nome_e_zona_encurtados(self):
        self.store.data["items"].append({"id": "x-1", "room": "sala", "name": "N" * 300, "zone": "Z" * 100})
        it = self.itens()["x-1"]
        self.assertEqual((len(it["nome"]), len(it["zona"])), (120, 60))

    def test_sem_zona_e_sem_nome_vao_vazios(self):
        self.store.data["items"].append({"id": "x-1", "room": "sala", "name": None, "zone": None})
        it = self.itens()["x-1"]
        self.assertEqual((it["nome"], it["zona"]), ("", ""))

    def test_valor_em_tem_so_a_data(self):
        for it in self.resposta()["itens"]:
            self.assertRegex(it["valor_em"], r"^\d{4}-\d{2}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
