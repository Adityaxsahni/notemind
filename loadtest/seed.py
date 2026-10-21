"""Seed the database for a load test: one shared course and N students who can read it.

Runs inside the backend container, as the database owner (like `app.admin`):

    docker compose exec -T backend python - --students 3000 < loadtest/seed.py

Idempotent: existing load-test users are reused. Every student gets the same password
(LOADTEST_PASSWORD, default below), hashed once, so seeding 10,000 users takes seconds.
Remove everything afterwards with `--cleanup`.
"""

import argparse
import hashlib
import os
import uuid

from sqlalchemy import create_engine, delete, insert, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.embeddings import get_embedder
from app.models import (
    Chunk,
    Collection,
    CollectionMember,
    Document,
    DocumentKind,
    DocumentStatus,
    Role,
    User,
)
from app.security.passwords import hash_password

DOMAIN = "loadtest.example.com"
OWNER_EMAIL = f"owner@{DOMAIN}"
COURSE = "Load test: Cell Biology 101"
PASSWORD = os.environ.get(
    "LOADTEST_PASSWORD", "Load-test-password-2026"
)  # pragma: allowlist secret

# A short study guide: enough passages for hybrid search and reranking to do real work.
NOTES = [
    (
        "Cell structure",
        "The cell membrane is a phospholipid bilayer with embedded proteins. "
        "It is selectively permeable: small nonpolar molecules diffuse across it, while ions "
        "and large polar molecules need channel or carrier proteins.",
    ),
    (
        "Cell structure",
        "The nucleus stores DNA as chromatin and is surrounded by a double "
        "membrane, the nuclear envelope, with pores that control traffic of RNA and proteins.",
    ),
    (
        "Organelles",
        "Mitochondria produce most of the cell's ATP through oxidative "
        "phosphorylation. They have their own circular DNA, which supports the endosymbiotic "
        "theory of their origin.",
    ),
    (
        "Organelles",
        "The rough endoplasmic reticulum is studded with ribosomes and makes "
        "secreted and membrane proteins; the smooth ER makes lipids and detoxifies drugs.",
    ),
    (
        "Organelles",
        "The Golgi apparatus modifies, sorts and packages proteins into vesicles "
        "for secretion or delivery to lysosomes.",
    ),
    (
        "Organelles",
        "Lysosomes contain hydrolytic enzymes that work at acidic pH and break "
        "down worn-out organelles, a process called autophagy.",
    ),
    (
        "Cell energy",
        "Glycolysis splits one glucose into two pyruvate in the cytoplasm, "
        "yielding a net 2 ATP and 2 NADH, and does not need oxygen.",
    ),
    (
        "Cell energy",
        "The Krebs cycle runs in the mitochondrial matrix and oxidises acetyl-CoA "
        "to carbon dioxide, producing NADH and FADH2 for the electron transport chain.",
    ),
    (
        "Cell energy",
        "The electron transport chain pumps protons across the inner "
        "mitochondrial membrane; ATP synthase uses that gradient to make ATP (chemiosmosis).",
    ),
    (
        "Photosynthesis",
        "In the light reactions, chlorophyll absorbs light, water is split and "
        "oxygen released, and ATP and NADPH are made in the thylakoid membranes.",
    ),
    (
        "Photosynthesis",
        "The Calvin cycle in the stroma fixes carbon dioxide with the enzyme "
        "RuBisCO and uses ATP and NADPH to build glyceraldehyde-3-phosphate.",
    ),
    (
        "Cell division",
        "Mitosis has four phases: prophase, metaphase, anaphase and telophase. "
        "It produces two genetically identical diploid daughter cells.",
    ),
    (
        "Cell division",
        "Meiosis has two divisions and produces four haploid gametes. Crossing "
        "over in prophase I and independent assortment create genetic variation.",
    ),
    (
        "Cell division",
        "Checkpoints at G1, G2 and the spindle assembly stage stop the cycle "
        "when DNA is damaged; failures of this control can lead to cancer.",
    ),
    (
        "Genetics",
        "DNA replication is semi-conservative. Helicase unwinds the helix, primase "
        "lays RNA primers and DNA polymerase adds nucleotides in the 5' to 3' direction.",
    ),
    (
        "Genetics",
        "Transcription copies a gene into messenger RNA; translation at the ribosome "
        "reads codons and tRNA brings the matching amino acids.",
    ),
    (
        "Transport",
        "Osmosis is the diffusion of water across a selectively permeable membrane "
        "from low solute concentration to high solute concentration.",
    ),
    (
        "Transport",
        "Active transport moves substances against their concentration gradient "
        "using ATP; the sodium-potassium pump moves 3 Na+ out and 2 K+ in.",
    ),
    (
        "Enzymes",
        "Enzymes lower activation energy. Competitive inhibitors bind the active "
        "site, while non-competitive inhibitors bind elsewhere and change the enzyme's shape.",
    ),
    (
        "Enzymes",
        "Temperature and pH affect enzyme activity; beyond the optimum the enzyme "
        "denatures and the active site loses its shape.",
    ),
]


def student_email(i: int) -> str:
    return f"student{i}@{DOMAIN}"


def seed(session: Session, students: int) -> None:
    password_hash = hash_password(PASSWORD)
    owner = session.scalar(select(User).where(User.email == OWNER_EMAIL))
    if owner is None:
        owner = User(email=OWNER_EMAIL, password_hash=password_hash)
        session.add(owner)
        session.flush()

    course = session.scalar(
        select(Collection).where(Collection.owner_id == owner.id, Collection.name == COURSE)
    )
    if course is None:
        course = Collection(owner_id=owner.id, name=COURSE)
        session.add(course)
        session.flush()
        session.add(CollectionMember(collection_id=course.id, user_id=owner.id, role=Role.OWNER))
        _add_notes(session, owner, course)

    existing = set(session.scalars(select(User.email).where(User.email.like(f"student%@{DOMAIN}"))))
    new = [
        {"id": uuid.uuid4(), "email": student_email(i), "password_hash": password_hash}
        for i in range(students)
        if student_email(i) not in existing
    ]
    for start in range(0, len(new), 1000):
        batch = new[start : start + 1000]
        session.execute(insert(User), batch)
        session.execute(
            insert(CollectionMember),
            [{"collection_id": course.id, "user_id": u["id"], "role": Role.VIEWER} for u in batch],
        )
    session.commit()
    print(f"course {course.id}: {len(existing) + len(new)} students ({len(new)} new)")


def _add_notes(session: Session, owner: User, course: Collection) -> None:
    body = "\n".join(text for _, text in NOTES).encode()
    document = Document(
        collection_id=course.id,
        uploaded_by=owner.id,
        filename="cell-biology-notes.pdf",
        kind=DocumentKind.PDF,
        size_bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        storage_key=uuid.uuid4().hex,  # no file on disk; the passages are inserted directly
        status=DocumentStatus.READY,
        progress=100,
        page_count=len(NOTES) // 2,
    )
    session.add(document)
    session.flush()
    embedder = get_embedder()
    vectors = embedder.embed_documents([f"{heading}\n{text}" for heading, text in NOTES])
    session.add_all(
        Chunk(
            user_id=owner.id,
            collection_id=course.id,
            document_id=document.id,
            position=i,
            page=i // 2 + 1,
            heading=heading,
            text=text,
            token_count=embedder.count_tokens(text),
            embedding=vector,
        )
        for i, ((heading, text), vector) in enumerate(zip(NOTES, vectors, strict=True))
    )


def cleanup(session: Session) -> None:
    # Cascades remove the course, its document, chunks and memberships.
    removed = session.execute(delete(User).where(User.email.like(f"%@{DOMAIN}"))).rowcount
    session.commit()
    print(f"removed {removed} load-test users")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--students", type=int, default=3000)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    # Owner connection (no SET ROLE): seeding writes other users' rows, which RLS forbids.
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        cleanup(session) if args.cleanup else seed(session, args.students)


if __name__ == "__main__":
    main()
