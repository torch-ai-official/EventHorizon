# scripts/ver_loss.py
import sqlite3
import matplotlib.pyplot as plt

conn = sqlite3.connect("data/mentes.db")
cursor = conn.execute("""
    SELECT timestamp, loss 
    FROM performance 
    WHERE loss IS NOT NULL 
    ORDER BY timestamp 
    LIMIT 5000
""")
dados = cursor.fetchall()

if dados:
    timestamps = [i for i in range(len(dados))]
    losses = [d[1] for d in dados]
    
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, losses, 'b-', alpha=0.5)
    plt.plot(timestamps, losses, 'b.', markersize=1)
    plt.xlabel('Previsão #')
    plt.ylabel('Loss (Erro)')
    plt.title('Curva de Aprendizado da IA')
    plt.grid(True, alpha=0.3)
    
    # Média móvel
    window = 100
    if len(losses) > window:
        moving_avg = [sum(losses[i:i+window])/window for i in range(len(losses)-window)]
        plt.plot(range(window//2, len(losses)-window//2), moving_avg, 'r-', linewidth=2, label='Média móvel')
    
    plt.legend()
    plt.show()
else:
    print("Sem dados de loss ainda")