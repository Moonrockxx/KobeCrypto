import sys, os
# Ajoute la racine du repo au chemin d'import pour que `import kobe` marche en tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
