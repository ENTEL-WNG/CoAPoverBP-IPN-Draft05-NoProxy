from pathlib import Path
import json

REPO = Path(__file__).resolve().parents[2]
PAYLOAD_DIR = REPO / "Results/congestion/Experiment_C/payloads"

def read_observation(size, message_id):
    filename = f"science_{size:04d}_m{message_id}.json"
    path = PAYLOAD_DIR / filename

    payload = path.read_bytes()

    if len(payload) != size:
        raise ValueError("Incorrect payload size")

    observation = json.loads(payload)

    if observation.get("sol") != 42:
        raise ValueError("Invalid Science observation")

    return payload

if __name__ == "__main__":
    for message_id in [1, 2]:
        payload = read_observation(50, message_id)
        print(f"Message {message_id}: {len(payload)} bytes | PASS")
