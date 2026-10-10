"""Test card rendering across cultural pillars and palettes."""
from pathlib import Path
import sys

# Ensure src is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telugu_agent import imagegen

samples = [
    (
        '"పిట్ట కొంచెం కూత ఘనం"\nరూపంలో చిన్నదైనా ప్రతిభలో గొప్పగా ఉండవచ్చనేది ఈ సామెత అంతరార్థం.\nమనిషి ఔన్నత్యం బాహ్య రూపంలో కాదు, వారు చేసే సత్కార్యాలలోనే దాగి ఉంటుంది.',
        "sample_saametha",
    ),
    (
        '"లేపాక్షి వేలాడే స్తంభం రహస్యం"\nశతాబ్దాల నాటి విజయనగర శిల్పకళా అద్భుతం.\nనేలను తాకకుండా గాలిలో వేలాడే ఈ స్తంభం నేటికీ ఆధునిక ఇంజనీర్లను విస్మయపరుస్తోంది.',
        "sample_architecture",
    ),
    (
        '"కాకతీయుల గొలుసుకట్టు చెరువులు"\nవర్షపు నీటిని ఒడిసిపట్టేందుకు వేల ఏళ్ల నాడే అద్భుత ఇంజనీరింగ్ వ్యవస్థ.\nఒక చెరువు నిండితే మరొక చెరువులోకి నీరు ప్రవహించే అద్భుత సాంకేతికత.',
        "sample_history",
    ),
]

out = Path("data/dryrun/images")
for text, pid in samples:
    path = imagegen.render(text, pid, out)
    print(f"Generated: {path}")
