#!/usr/bin/env python3
"""
Script simple pour lister les fichiers d'un dossier.

Utilisation:
    python list_files.py [dossier]

Si aucun dossier n'est spécifié, le dossier courant est utilisé.
"""

import os
import sys


def lister_fichiers(dossier: str = ".") -> None:
    """
    Liste les fichiers d'un dossier donné.

    Args:
        dossier (str): Chemin vers le dossier à lister. Par défaut, le dossier courant.
    """
    try:
        # Vérifier si le dossier existe
        if not os.path.exists(dossier):
            print(f"Erreur: Le dossier '{dossier}' n'existe pas.")
            return

        # Vérifier si le chemin est bien un dossier
        if not os.path.isdir(dossier):
            print(f"Erreur: '{dossier}' n'est pas un dossier.")
            return

        # Lister les fichiers et dossiers
        print(f"\nContenu du dossier '{dossier}':\n")
        for element in os.listdir(dossier):
            chemin = os.path.join(dossier, element)
            if os.path.isfile(chemin):
                print(f"[Fichier] {element}")
            else:
                print(f"[Dossier] {element}")

    except Exception as e:
        print(f"Une erreur est survenue: {e}")


if __name__ == "__main__":
    # Récupérer le dossier depuis les arguments ou utiliser le dossier courant
    dossier = sys.argv[1] if len(sys.argv) > 1 else "."

    # Lister les fichiers
    lister_fichiers(dossier)
