from rich.console import Console
from rich.text import Text

# Liste de 10 phrases poétiques
poem_phrases = [
    "La nuit s'étire comme un voile de soie,",
    "Les étoiles murmurent des secrets anciens,",
    "Le vent danse avec les feuilles tombées,",
    "L'aube se lève, timide et dorée,",
    "Les nuages peignent le ciel de rêves,",
    "La rivière chante une mélodie éternelle,",
    "Les ombres s'allongent au crépuscule,",
    "La lune veille sur les cœurs solitaires,",
    "L'horizon s'embrase de mille feux,",
    "Et le monde s'endort dans un souffle léger."
]

def get_blue_shade(intensity: int) -> str:
    """Retourne une nuance de bleu en hexadécimal."""
    # Dégradé du bleu foncé (#00008B) au bleu clair (#ADD8E6)
    base_blue = (0, 0, 139)  # Bleu foncé
    light_blue = (173, 216, 230)  # Bleu clair

    # Interpolation linéaire entre les deux couleurs
    r = int(base_blue[0] + (light_blue[0] - base_blue[0]) * intensity / 100)
    g = int(base_blue[1] + (light_blue[1] - base_blue[1]) * intensity / 100)
    b = int(base_blue[2] + (light_blue[2] - base_blue[2]) * intensity / 100)

    return f"#{r:02x}{g:02x}{b:02x}"

def main():
    console = Console()
    for i, phrase in enumerate(poem_phrases):
        text = Text()
        for j, char in enumerate(phrase):
            intensity = (i * 10 + j) % 100  # Décalage pour chaque phrase
            color = get_blue_shade(intensity)
            text.append(char, style=color)
        console.print(text)

if __name__ == "__main__":
    main()