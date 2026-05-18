import subprocess
import os

def run_command(command, description):
    print(f"\n[+] Exécution: {description}")
    try:
        # Utilisation de shell=True pour les commandes complexes/pipes
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=60)
        print(result.decode('utf-8', errors='ignore'))
    except subprocess.TimeoutExpired:
        print("Erreur: La commande a expiré.")
    except subprocess.CalledProcessError as e:
        print(f"Erreur: {e.output.decode('utf-8', errors='ignore')}")

def main():
    print("=== DÉMARRAGE DU DIAGNOSTIC COMPLET DU VPS ===")
    
    # 1. État général
    run_command("uname -a", "Informations noyau")
    run_command("lsb_release -a", "Version distribution")
    run_command("free -h", "Mémoire RAM")
    run_command("df -h", "Espace disque")
    
    # 2. Réseau
    run_command("ping -c 4 google.com", "Connectivité Internet")
    run_command("curl -I https://google.com", "En-tête HTTP Google")
    run_command("ss -tulnp", "Ports ouverts")
    
    # 3. Performance (Note: certains outils comme stress-ng ou sysbench demandent installation)
    run_command("mpstat -P ALL 1 1", "Statistiques CPU")
    
    # Test disque (écriture/lecture rapide)
    run_command("dd if=/dev/zero of=./testfile bs=1M count=100 oflag=direct && dd if=./testfile of=/dev/null bs=1M count=100 iflag=direct && rm -f ./testfile", "Test I/O Disque")

    # 4. Services
    run_command("systemctl status nginx", "Status Nginx (peut échouer si non installé)")
    
    # 5. Sécurité
    run_command("apt list --upgradable", "Mises à jour disponibles")
    run_command("sudo ufw status", "Statut pare-feu UFW")
    run_command("sudo iptables -L -n -v | head -n 20", "Règles IPTables (extrait)")

    print("\n=== DIAGNOSTIC TERMINÉ ===")

if __name__ == "__main__":
    main()
