"""A Memória da IA (memoria_ia.py, igual nos apps em Python): uma lista só, da casa, na pasta share, que todo app lê e escreve."""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from _boot import server as S

M = S.memoria_ia


class TestMemoria(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.arq = os.path.join(self.dir, "familia", "memoria_ia.json")
        M._GUARDADO.clear()
        self.addCleanup(M._GUARDADO.clear)

    def test_guardar_ler_apagar_e_o_bloco_da_ia(self):
        self.assertEqual((M.ler(self.arq), M.para_a_ia(self.arq)), ([], ""))
        lista = M.lembrar("  Creme é   sempre Higiene ", "InventarIA", "Ana", self.arq)
        self.assertEqual([(x["texto"], x["app"], x["quem"]) for x in lista], [("Creme é sempre Higiene", "InventarIA", "Ana")])
        self.assertRegex(lista[0]["id"], r"^[0-9a-f]{8}$")
        self.assertRegex(lista[0]["em"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d{4}$")
        self.assertEqual(len(M.lembrar("creme é sempre higiene", "ResolvIA", arquivo=self.arq)), 1, "a mesma frase não entra duas vezes")
        M.lembrar("A feira é no sábado", "ResolvIA", arquivo=self.arq)
        with open(self.arq, encoding="utf-8") as f:
            gravado = json.load(f)
        self.assertEqual((gravado["versao"], [x["app"] for x in gravado["lista"]], "quem" in gravado["lista"][1]), (1, ["InventarIA", "ResolvIA"], False))
        self.assertEqual(oct(os.stat(self.arq).st_mode & 0o777), "0o600")
        self.assertEqual(M.para_a_ia(self.arq), M.TITULO + "\n- Creme é sempre Higiene\n- A feira é no sábado")
        self.assertEqual([x["texto"] for x in M.esquecer(lista[0]["id"], self.arq)], ["A feira é no sábado"])
        self.assertEqual(len(M.esquecer("nao-existe", self.arq)), 1)
        for ruim in ("", " a ", None):
            with self.assertRaisesRegex(M.ErroMemoria, "Escreva o que é para lembrar"):
                M.lembrar(ruim, "X", arquivo=self.arq)
        with mock.patch.object(M, "MAX_FRASES", 1), self.assertRaisesRegex(M.ErroMemoria, "A memória já tem 1 frases. Apague alguma."):
            M.lembrar("Mais uma coisa", "X", arquivo=self.arq)
        self.assertEqual(len(M.lembrar("x" * 300, "X", arquivo=self.arq)[-1]["texto"]), 240)

    def test_outro_app_escreveu_e_o_arquivo_estragado(self):
        M.lembrar("A feira é no sábado", "ResolvIA", arquivo=self.arq)
        # outro app (outro processo) grava por fora: quem lê vê em até 30 segundos; quem escreve lê de novo antes
        with open(self.arq, "w", encoding="utf-8") as f:
            json.dump({"versao": 1, "lista": [{"id": "a1", "texto": "O lixo sai na terça", "app": "CronologIA"}, "x", {"texto": "ab"}, {"id": "a2", "texto": "o lixo sai na TERÇA"}]}, f)
        agora = M._GUARDADO[self.arq][0]
        self.assertEqual([x["texto"] for x in M.ler(self.arq, agora + 5)], ["A feira é no sábado"], "ainda o que estava guardado")
        self.assertEqual([x["texto"] for x in M.ler(self.arq, agora + 40)], ["O lixo sai na terça"], "relido: só as frases que valem, sem a repetida")
        self.assertEqual([x["texto"] for x in M.lembrar("Creme é Higiene", "InventarIA", arquivo=self.arq)], ["O lixo sai na terça", "Creme é Higiene"])
        M._GUARDADO.clear()
        with open(self.arq, "w", encoding="utf-8") as f:
            f.write("{estragado")
        self.assertEqual(M.ler(self.arq), [])
        with open(self.arq, "w", encoding="utf-8") as f:
            f.write('{"lista": "não é lista"}')
        self.assertEqual(M.ler(self.arq, fresco=True), [])
        # a pasta share só para leitura: o erro diz
        with mock.patch.object(M.os, "replace", side_effect=OSError(30, "Read-only file system")), \
                self.assertRaisesRegex(M.ErroMemoria, "Não consegui gravar a memória na pasta share \\(Read-only file system\\)"):
            M.lembrar("Não grava", "X", arquivo=self.arq)

    def test_juntar_o_que_um_app_guardava_antes(self):
        M.lembrar("A feira é no sábado", "ResolvIA", arquivo=self.arq)
        n = M.juntar([{"texto": "a feira é no sábado"}, {"texto": "O lixo sai na terça", "em": "2026-11-20T10:00:00-0300", "quem": "Beto"}, "Creme é Higiene", {"texto": ""}], "CorrerIA", self.arq)
        self.assertEqual(n, 2)
        self.assertEqual([(x["texto"], x["app"], x.get("quem", "")) for x in M.ler(self.arq)],
                         [("A feira é no sábado", "ResolvIA", ""), ("O lixo sai na terça", "CorrerIA", "Beto"), ("Creme é Higiene", "CorrerIA", "")])
        self.assertEqual(M.juntar([], "CorrerIA", self.arq), 0)
        self.assertEqual(M.juntar(None, "CorrerIA", self.arq), 0)

    def test_a_pasta_que_nao_existe_nao_prende_o_app(self):
        """O caminho da memória dentro de um arquivo (uma pasta share estragada): diz que não gravou, sem ficar esperando a vez
        para sempre."""
        import time
        os.makedirs(self.dir, exist_ok=True)
        preso = os.path.join(self.dir, "arquivo.txt")
        with open(preso, "w") as f:
            f.write("x")
        t0 = time.monotonic()
        with mock.patch.object(M, "ESPERA_SEG", 0.2), self.assertRaisesRegex(M.ErroMemoria, "Não consegui gravar a memória na pasta share"):
            M.lembrar("não tem onde gravar", "CorrerIA", arquivo=os.path.join(preso, "familia", "memoria_ia.json"))
        self.assertLess(time.monotonic() - t0, 3)

    def test_a_vez_de_gravar_entre_os_apps(self):
        """Dois apps gravando no mesmo instante: cada um espera a vez (a pasta .trava ao lado do arquivo) e nenhuma frase se
        perde. Uma trava que ficou de um app que caiu sai sozinha; sem conseguir a vez, grava assim mesmo."""
        import subprocess
        import sys
        import time
        codigo = ("import sys; sys.path.insert(0, sys.argv[1]); import memoria_ia as M\n"
                  "for i in range(15): M.lembrar(f'frase {sys.argv[3]} número {i}', 'App' + sys.argv[3], arquivo=sys.argv[2])\n")
        pasta = os.path.dirname(os.path.abspath(M.__file__))
        ps = [subprocess.Popen([sys.executable, "-c", codigo, pasta, self.arq, str(n)]) for n in range(4)]
        self.assertEqual([p.wait(60) for p in ps], [0, 0, 0, 0])
        self.assertEqual(len(M.ler(self.arq, fresco=True)), 60, "as 60 frases dos quatro, nenhuma perdida")
        self.assertEqual(sorted(os.listdir(os.path.dirname(self.arq))), ["memoria_ia.json"], "sem trava nem arquivo temporário para trás")
        M.esquecer(M.ler(self.arq, fresco=True)[0]["id"], self.arq)
        # a trava de um app que caiu (velha) sai; a de agora é esperada e, sem a vez, grava assim mesmo
        trava = self.arq + ".trava"
        os.mkdir(trava)
        os.utime(trava, (time.time() - 60, time.time() - 60))
        self.assertEqual(len(M.lembrar("depois da trava velha", "CorrerIA", arquivo=self.arq)), 60)
        self.assertFalse(os.path.exists(trava))
        M.esquecer(M.ler(self.arq, fresco=True)[0]["id"], self.arq)
        os.mkdir(trava)
        with mock.patch.object(M, "ESPERA_SEG", 0.05):
            self.assertEqual(len(M.lembrar("sem a vez, grava assim mesmo", "CorrerIA", arquivo=self.arq)), 60)
        self.assertTrue(os.path.isdir(trava), "a trava de outro app não é tirada por quem não a pôs")
        os.rmdir(trava)
        # a pasta share que não deixa criar a trava: grava do mesmo jeito
        M.esquecer(M.ler(self.arq, fresco=True)[0]["id"], self.arq)
        with mock.patch.object(M.os, "mkdir", side_effect=PermissionError("não pode")):
            self.assertEqual(len(M.lembrar("sem poder criar a trava", "CorrerIA", arquivo=self.arq)), 60)


if __name__ == "__main__":
    unittest.main()
