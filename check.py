import sys, traceback
sys.stderr = sys.stdout

try:
    from database import init_db, SessionLocal, User
    from auth import hash_password, verify_password, create_access_token
    from encryption import encrypt, decrypt
    print("1. Imports OK")

    init_db()
    print("2. DB OK")

    h = hash_password("mypassword")
    assert verify_password("mypassword", h)
    print("3. bcrypt OK:", h[:15])

    e = encrypt("brokerpass")
    assert decrypt(e) == "brokerpass"
    print("4. Encryption OK")

    tok = create_access_token({"sub": "1"})
    print("5. JWT OK:", tok[:20])

    db = SessionLocal()
    existing = db.query(User).filter(User.email == "final@test.com").first()
    if existing:
        db.delete(existing)
        db.commit()
    u = User(email="final@test.com", hashed_password=hash_password("pass123"))
    db.add(u)
    db.commit()
    db.refresh(u)
    print("6. Register flow OK, user id:", u.id)
    db.close()

    print("\nALL CHECKS PASSED")

except Exception:
    traceback.print_exc()
