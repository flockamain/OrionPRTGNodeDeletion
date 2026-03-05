import requests
import urllib3
from orionsdk import SwisClient
import config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PRTG_SERVER = config.PRTG_SERVER    # e.g., https://prtg.company.net
ORION_SERVER = config.ORION_SERVER   # e.g., your-orion-server.company.net -- https:// is automatically added as prefix
PRTG_USER = config.PRTG_USER
PRTG_PASS = config.PRTG_PASS
ORION_USER = config.ORION_USER
ORION_PASS = config.ORION_PASS

#test both logins


def test_prtg_login():
    url = f"{PRTG_SERVER}/api/table.json"
    params = {'username': PRTG_USER, 'passhash': PRTG_PASS}
    try:
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status()
        data = response.json()
        if 'error' in data:
            print(f"PRTG login rejected: {data.get('error')}")
            return False
        print(f"  ✓ PRTG connected | Version: {data.get('prtg-version')} | Total Devices: {data.get('treesize')}")
        return True
    except requests.exceptions.Timeout:
        print(f"PRTG connection timed out -- is the server reachable?")
        return False
    except requests.exceptions.ConnectionError:
        print(f"PRTG connection error -- could not reach {PRTG_SERVER}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  ✗ PRTG connection failed: {e}")
        return False

def test_orion_login():
    try:
        swis = SwisClient(ORION_SERVER, ORION_USER, ORION_PASS, verify=False)
        result = swis.query("SELECT COUNT(*) AS NodeCount FROM Orion.Nodes")
        node_count = result['results'][0]['NodeCount']
        print(f"  ✓ Orion connected | Total Nodes: {node_count}")
        return swis
    except Exception as e:
        print(f"  ✗ Orion connection failed: {e}")
        return None

#prtg

def get_all_prtg_devices():
    url = f"{PRTG_SERVER}/api/table.json"
    all_devices = []
    start = 0

    while True:
        params = {
            'content': 'devices',
            'output': 'json',
            'columns': 'objid,device',
            'username': PRTG_USER,
            'passhash': PRTG_PASS,
            'count': 2500,
            'start': start
        }
        try:
            response = requests.get(url, params=params, verify=False)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"PRTG fetch failed at offset {start}: {e}")
            return all_devices
        
        devices = data.get('devices', [])
        all_devices.extend(devices)

        treesize = data.get('treesize', 0)

        if treesize == 0:
            break

        print(f"Fetched {len(all_devices)} / {treesize} PRTG devices")

        if len(all_devices) >= treesize:
            break

        start += 2500

    return all_devices

def search_prtg(search_term):
    if not PRTG_USER or not PRTG_PASS:
        return []
    try:
        devices = get_all_prtg_devices()
        mapping = [d for d in devices if search_term in d['device'].lower()]
        return mapping
    except Exception as e:
        print(f"PRTG search failed: {e}")
        return []

def delete_prtg_device(objid, device_name):
    url = f"{PRTG_SERVER}/api/deleteobject.htm"
    params = {
        'id': objid,
        'approve': 1,
        'username': PRTG_USER,
        'passhash': PRTG_PASS
    }
    try:
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status()
        print(f"  ✓ Successfully deleted from PRTG: {device_name} (ID: {objid})")
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Failed to delete from PRTG: {e}")

#orion

def search_orion(swis, search_term):

    if not swis:
        return []
    try:
        result = swis.query(
            "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE @name",
            name=f"%{search_term}%"
        )
        return result['results']
    except Exception as e:
        print(f"Orion search failed: {e}")
        return []

def delete_orion_node(swis, node_id, node_name):
    if not swis:
        print("Orion session unavailable - cannot delete")
        return
    node_uri = f"swis://orion/Orion/Orion.Nodes/NodeID={node_id}"
    try:
        swis.delete(node_uri)
        print(f"  ✓ Successfully deleted from Orion: {node_name} (NodeID: {node_id})")
    except Exception as e:
        print(f"  ✗ Failed to delete from Orion: {e}")

#search and delete

def confirm_delete(label):
    confirm = input(f"\nType 'YES I WANT TO DELETE THIS SINGLE NODE' to confirm deletion from {label}: ").strip()
    return confirm == "YES I WANT TO DELETE THIS SINGLE NODE"

def get_menu_choice(options):
    valid = [str(i) for i in range(1, len(options) + 1)]
    while True:
        choice = input(f"Enter {'/'.join(valid)}: ").strip()
        if choice in valid:
            return choice
        print(f"Invalid choice - Please enter one of the following: {', '.join(valid)}")

def search_and_delete(prtg_available, swis):
    while True:
        search_term = input("\nEnter the string to search for across both platforms: ").strip()

        #empty or whitespace-only search term -- ask to try diff search to try again
        if not search_term:
            print("No search term provided.")
            again = input("Would you like to try a different search? (yes/no): ").strip().lower()
            if again == 'yes':
                continue
            else:
                print("Exiting.")
                break

        #search term is too short -- warn user, but allow them to proceed
        #additional blockades will be in place further down the line
        if len(search_term) < 5:
            print("  Warning: search term is very short and may return a large number of results.")
            proceed = input("  Continue anyway? (yes/no): ").strip().lower()
            if proceed != 'yes':
                continue

        print(f"\nSearching both platforms for '{search_term}'...")
        prtg_matches  = search_prtg(search_term.lower()) if prtg_available else []
        orion_matches = search_orion(swis, search_term)

        #print results
        print(f"\n{'─'*40}")
        if prtg_available:
            print(f"PRTG   — {len(prtg_matches)} match(es) found:")
            for d in prtg_matches:
                print(f"  - {d['device']} (ID: {d['objid']})")
        else:
            print("PRTG   — unavailable")

        if swis:
            print(f"\nOrion  — {len(orion_matches)} match(es) found:")
            for n in orion_matches:
                print(f"  - {n['Caption']} (NodeID: {n['NodeID']}, IP: {n['IPAddress']})")
        else:
            print("\nOrion  — unavailable")
        print(f"{'─'*40}")

        #determine if one or the other or both are deleteable
        prtg_deletable  = prtg_available and len(prtg_matches) == 1
        orion_deletable = swis is not None and len(orion_matches) == 1
        prtg_blocked    = prtg_available and len(prtg_matches) > 1
        orion_blocked   = swis is not None and len(orion_matches) > 1

        if prtg_blocked:
            print("\nPRTG: Multiple matches found — refine your search to a single result before deleting.")
        if orion_blocked:
            print("\nOrion: Multiple matches found — refine your search to a single result before deleting.")

        #nothing to delete
        if not prtg_deletable and not orion_deletable:
            print("\nNo single-match results to delete on either platform.")

        else:
            #ask what to delete
            print("\nWhat would you like to delete?")
            if prtg_deletable and orion_deletable:
                print("  1. Delete from both PRTG and Orion")
                print("  2. Delete from PRTG only")
                print("  3. Delete from Orion only")
                print("  4. Skip deletion")
                choice = get_menu_choice([1, 2, 3, 4])
            elif prtg_deletable:
                print("  (Orion: no single match — only PRTG deletion available)")
                print("  1. Delete from PRTG")
                print("  2. Skip deletion")
                choice = get_menu_choice([1, 2])
                choice = 'prtg_only' if choice == '1' else '4'
            else:
                print("  (PRTG: no single match — only Orion deletion available)")
                print("  1. Delete from Orion")
                print("  2. Skip deletion")
                choice = get_menu_choice([1, 2])
                choice = 'orion_only' if choice == '1' else '4'

            #execute deletions upon confirmation
            if choice == '1':
                if confirm_delete("PRTG and Orion"):
                    delete_prtg_device(prtg_matches[0]['objid'], prtg_matches[0]['device'])
                    delete_orion_node(swis, orion_matches[0]['NodeID'], orion_matches[0]['Caption'])
                else:
                    print("Delete cancelled.")
            elif choice == '2' and prtg_deletable and orion_deletable:
                if confirm_delete("PRTG"):
                    delete_prtg_device(prtg_matches[0]['objid'], prtg_matches[0]['device'])
                else:
                    print("Delete cancelled.")
            elif choice == '3':
                if confirm_delete("Orion"):
                    delete_orion_node(swis, orion_matches[0]['NodeID'], orion_matches[0]['Caption'])
                else:
                    print("Delete cancelled.")
            elif choice == 'prtg_only':
                if confirm_delete("PRTG"):
                    delete_prtg_device(prtg_matches[0]['objid'], prtg_matches[0]['device'])
                else:
                    print("Delete cancelled.")
            elif choice == 'orion_only':
                if confirm_delete("Orion"):
                    delete_orion_node(swis, orion_matches[0]['NodeID'], orion_matches[0]['Caption'])
                else:
                    print("Delete cancelled.")
            elif choice == '4':
                print("Deletion skipped.")

        #ask to search again
        again = input("\nWould you like to search for another node? (yes/no): ").strip().lower()
        if again != 'yes':
            print("Exiting. Sessions closed.")
            break
# main
if __name__ == '__main__':
    #validate the credentials are present in config.py
    missing = []
    if not config.PRTG_SERVER: missing.append('PRTG_SERVER')
    if not config.PRTG_USER: missing.append('PRTG_USER')
    if not config.PRTG_PASS: missing.append('PRTG_PASS')
    if not config.ORION_SERVER: missing.append('ORION_SERVER')
    if not config.ORION_USER: missing.append('ORION_USER')
    if not config.ORION_PASS: missing.append('ORION_PASS')

    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Please check your config.py file")
        exit(1)
    
    print("\nConnecting to both platforms...")
    prtg_ok = test_prtg_login()
    swis    = test_orion_login()

    if not prtg_ok and not swis:
        print("\nFailed to connect to both platforms. Exiting.")
    elif not prtg_ok:
        print("\nWarning: PRTG unavailable. Continuing with Orion only.")
        search_and_delete(False, swis)
    elif not swis:
        print("\nWarning: Orion unavailable. Continuing with PRTG only.")
        search_and_delete(True, None)
    else:
        search_and_delete(True, swis)