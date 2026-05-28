# scripts/migrar_para_sql.py
import sys
import os
import json
import torch
from collections import deque

# Adiciona o projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Software.core.mind_sql import BancoMentesSQL
from Software.core.mind_pytorch import MenteTorch

def migrar_tudo():
    print("=" * 60)
    print("🔥 MIGRANDO 300 MODELOS PYTORCH PARA SQL")
    print("=" * 60)
    
    # 1. Inicializa banco SQL
    db = BancoMentesSQL()
    
    # 2. Carrega minds.json (estatísticas)
    minds_json_path = "data/minds.json"
    if os.path.exists(minds_json_path):
        with open(minds_json_path, "r") as f:
            minds_data = json.load(f)
        print(f"\n📊 minds.json carregado: {len(minds_data.get('mentes', {}))} mentes")
    else:
        print("⚠️ minds.json não encontrado")
        minds_data = {"mentes": {}}
    
    # 3. Pasta dos modelos PyTorch
    pytorch_folder = "data/mentes_pytorch"
    
    # 4. Migra cada modelo
    migrados = 0
    erros = 0
    ignorados = 0
    
    # Primeiro, tenta os modelos da pasta .pt
    if os.path.exists(pytorch_folder):
        arquivos = [f for f in os.listdir(pytorch_folder) if f.endswith('.pt')]
        print(f"\n📁 Encontrados {len(arquivos)} arquivos .pt em {pytorch_folder}")
        
        for arquivo in arquivos:
            try:
                # Extrai ID do nome do arquivo (mente_296.pt)
                id_str = arquivo.replace('mente_', '').replace('.pt', '')
                id_agente = int(id_str)
                
                # Carrega o modelo .pt
                checkpoint = torch.load(os.path.join(pytorch_folder, arquivo))
                
                # Prepara estatísticas
                stats = {
                    'tipo': 'pytorch',
                    'n_acertos': checkpoint.get('n_acertos', 0),
                    'n_erros': checkpoint.get('n_erros', 0),
                    'geracao': checkpoint.get('geracao', 0),
                    'accuracy': checkpoint.get('n_acertos', 0) / max(1, checkpoint.get('n_acertos', 0) + checkpoint.get('n_erros', 0)),
                    'historico_loss': checkpoint.get('historico_loss', [])
                }
                
                # Serializa os pesos para bytes
                import io
                buffer = io.BytesIO()
                torch.save(checkpoint['model_state_dict'], buffer)
                pesos_bytes = buffer.getvalue()
                
                buffer_opt = io.BytesIO()
                torch.save(checkpoint.get('optimizer_state_dict', {}), buffer_opt)
                optimizer_bytes = buffer_opt.getvalue()
                
                # Salva no SQL
                db.salvar_mente(id_agente, stats, pesos_bytes, optimizer_bytes)
                migrados += 1
                
                if migrados % 50 == 0:
                    print(f"   ✅ {migrados} modelos migrados...")
                    
            except Exception as e:
                print(f"   ❌ Erro ao migrar {arquivo}: {e}")
                erros += 1
    else:
        print(f"\n⚠️ Pasta {pytorch_folder} não encontrada")
    
    # 5. Também migra do minds.json (para pegar estatísticas de agentes sem .pt)
    print(f"\n📊 Processando mentes do minds.json...")
    for id_str, m_data in minds_data.get('mentes', {}).items():
        id_agente = int(id_str)
        
        # Verifica se já foi migrado
        dados = db.carregar_mente(id_agente)
        if dados:
            ignorados += 1
            continue
        
        try:
            stats = {
                'tipo': m_data.get('tipo', 'pytorch'),
                'n_acertos': m_data.get('n_acertos', 0),
                'n_erros': m_data.get('n_erros', 0),
                'geracao': m_data.get('geracao', 0),
                'accuracy': m_data.get('accuracy', 0.5),
                'historico_loss': []
            }
            
            # Pesos vazios (serão inicializados do zero)
            db.salvar_mente(id_agente, stats)
            migrados += 1
            
            if migrados % 50 == 0:
                print(f"   ✅ {migrados} modelos migrados (incluindo JSON)...")
                
        except Exception as e:
            print(f"   ❌ Erro ao migrar mente {id_agente}: {e}")
            erros += 1
    
    # 6. Registrar métricas
    db.registrar_metricas_diarias()
    
    # 7. Relatório final
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO DE MIGRAÇÃO")
    print("=" * 60)
    print(f"✅ Modelos migrados: {migrados}")
    print(f"⚠️ Ignorados (já existentes): {ignorados}")
    print(f"❌ Erros: {erros}")
    
    # 8. Verificar o banco
    estatisticas = db.get_estatisticas_gerais()
    print("\n📈 ESTATÍSTICAS DO BANCO SQL:")
    print(f"   Total de mentes: {estatisticas['total_mentes']}")
    print(f"   Total de previsões: {estatisticas['total_previsoes']}")
    print(f"   Acurácia global: {estatisticas['acurácia_global']:.1%}")
    
    # 9. Ranking
    ranking = db.get_ranking(limit=10)
    if ranking:
        print("\n🏆 TOP 10 IAs (Ranking):")
        for i, r in enumerate(ranking, 1):
            print(f"   {i}. IA {r['id']}: {r['acuracia']:.1%} ({r['n_acertos']}/{r['n_acertos']+r['n_erros']})")
    
    print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 60)
    
    return migrados, erros

if __name__ == "__main__":
    migrar_tudo()