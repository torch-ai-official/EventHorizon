# Cria uma string única concatenando todos os números de 0 a 7000
sequencia_gigante = "".join(str(n) for n in range(700001))

# Conta as ocorrências de "2026" na string completa
total = sequencia_gigante.count("2026")

print(f"A sequência '2026' aparece {total} vezes.")
