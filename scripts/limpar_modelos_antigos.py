# scripts/limpar_modelos_antigos.py
import os
import shutil

# Backup (opcional)
backup_dir = "backup_modelos_antigos"
os.makedirs(backup_dir, exist_ok=True)

# Move modelos antigos
if os.path.exists("data/mentes_pytorch"):
    shutil.move("data/mentes_pytorch", f"{backup_dir}/mentes_pytorch")
    print(f"✅ Modelos antigos movidos para {backup_dir}")

if os.path.exists("data/mentes.db"):
    shutil.move("data/mentes.db", f"{backup_dir}/mentes.db")
    print(f"✅ Banco antigo movido para {backup_dir}")

# Cria pastas novas
os.makedirs("data/mentes_pytorch", exist_ok=True)

print("✅ Ambiente limpo! Agora rode o sistema normalmente.")