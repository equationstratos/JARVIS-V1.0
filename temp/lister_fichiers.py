import os

def lister_fichiers(dossier):
    try:
        # Liste tous les éléments dans le dossier
        elements = os.listdir(dossier)
        
        print(f"Contenu du dossier '{dossier}':")
        for element in elements:
            print(f"- {element}")
    except FileNotFoundError:
        print(f"Erreur: Le dossier '{dossier}' n'existe pas.")
    except PermissionError:
        print(f"Erreur: Permission refusée pour accéder au dossier '{dossier}'.")

if __name__ == "__main__":
    # Vous pouvez changer '.' par le chemin de votre choix
    chemin = "."
    lister_fichiers(chemin)
