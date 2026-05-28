# scripts/test_sql.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Software.core.mind_sql import BancoMentesSQL

print("=" * 50)
print("🧪 TESTANDO BANCO DE DADOS SQL")
print("=" * 50)

# Criar banco
db = BancoMentesSQL()

# Inserir uma mente de teste
stats = {
    'tipo': 'pytorch',
    'n_acertos': 100,
    'n_erros': 80,
    'geracao': 1,
    'accuracy': 0.555,
    'historico_loss': [0.3, 0.28, 0.25, 0.22]
}

db.salvar_mente(999, stats, pesos_bytes=b'test_pesos', optimizer_bytes=b'test_opt')

# Carregar
dados = db.carregar_mente(999)
print(f"\n📊 Mente carregada:")
print(f"   ID: {dados['id']}")
print(f"   Acertos: {dados['n_acertos']}")
print(f"   Erros: {dados['n_erros']}")
print(f"   Acurácia: {dados['n_acertos']/(dados['n_acertos']+dados['n_erros']):.1%}")

print("\n✅ Banco de dados funcionando!")