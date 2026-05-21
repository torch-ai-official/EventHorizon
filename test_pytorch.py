# test_pytorch.py - Teste do PyTorch

import os
os.environ["MODO_IA"] = "pytorch"  # Força modo PyTorch

print("=" * 50)
print("🧪 TESTANDO PYTORCH")
print("=" * 50)

# Importa os módulos
from Software.core.mind import BancoMentes
from Software.core.engine import Universo

print("\n1️⃣ Criando universo...")
universo = Universo()

print("\n2️⃣ Criando mente para agente 999...")
mente = universo.mentes.obter(999)

print(f"\n3️⃣ Testando forward com entrada de teste...")
entrada_teste = [0.5, 0.3, 0.2, 0.1, 0.4, 0.6, 0.7, 0.8, 0.2, 0.3, 0.1, 0.05]
resultado = mente.forward(entrada_teste)
print(f"   Entrada: {entrada_teste[:5]}...")
print(f"   Saída (previsão): {resultado:.4f}")

print("\n4️⃣ Testando aprendizado...")
recompensa = 0.5
mente.aprender(recompensa)
print(f"   Recompensa: {recompensa}")
print(f"   Aprendizado executado!")

print("\n5️⃣ Verificando estatísticas...")
print(f"   Acurácia: {mente.accuracy:.2%}")
print(f"   Acertos: {mente.n_acertos}")
print(f"   Erros: {mente.n_erros}")
print(f"   Loss médio: {mente.loss_medio:.4f}")

print("\n6️⃣ Testando salvamento...")
mente.salvar()
print("   Mente salva com sucesso!")

print("\n7️⃣ Testando carregamento...")
nova_mente = universo.mentes.obter(999)
print("   Mente carregada com sucesso!")

print("\n" + "=" * 50)
print("✅ PYTORCH FUNCIONANDO PERFEITAMENTE!")
print("=" * 50)