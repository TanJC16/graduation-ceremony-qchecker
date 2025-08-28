# streamlit_app.py
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# ---------------------- Firebase init (cached) ----------------------
@st.cache_resource
def init_firebase():
    # Always load credentials from Streamlit secrets
    cfg = dict(st.secrets["firebase"])
    cfg["private_key"] = cfg["private_key"].replace("\\n", "\n")

    if not firebase_admin._apps:
        cred = credentials.Certificate(cfg)
        firebase_admin.initialize_app(cred)
    return firestore.client()


db = init_firebase()

# ---------------------- Helpers ----------------------
def get_student(doc_id: str):
    """Read a student document by its document ID (student_id)."""
    return db.collection("students").document(doc_id).get()

@firestore.transactional
def register_student_txn(transaction, doc_ref, expected_seat_num: int):
    """
    Atomically verify seat number and set registered=True.
    Also stamps registered_at (server time) and registered_via="streamlit".
    """
    snap = doc_ref.get(transaction=transaction)
    if not snap.exists:
        raise ValueError("Student not found.")

    data = snap.to_dict() or {}

    # Validate seat number matches Firestore record
    if int(data.get("seat_num", -1)) != int(expected_seat_num):
        raise ValueError("Seat number does not match our record.")

    # Already registered?
    if data.get("registered") is True:
        raise ValueError("This student is already registered.")

    # Update atomically
    transaction.update(doc_ref, {
        "registered": True,
        "registered_at": firestore.SERVER_TIMESTAMP,
        "registered_via": "streamlit"
    })

# ---------------------- UI ----------------------
st.set_page_config(page_title="Graduation Registration", page_icon="🎓", layout="centered")
st.title("🎓 Graduation Registration")
st.caption("Enter your Student ID and Seat Number to mark yourself as registered.")

with st.form("lookup_form", clear_on_submit=False):
    col1, col2 = st.columns([2, 1])
    with col1:
        student_id = st.text_input(
            "Student ID (Document ID)",
            placeholder="e.g. 24WMR09274"
        ).strip()
    with col2:
        seat_num = st.number_input("Seat Number", min_value=1, step=1)
    submitted = st.form_submit_button("Lookup")

if submitted:
    if not student_id:
        st.error("Please enter a Student ID.")
    else:
        doc = get_student(student_id)
        if not doc.exists:
            st.error("No student found with that ID.")
        else:
            data = doc.to_dict() or {}
            st.subheader("Record Preview")
            st.write({
                "name": data.get("name"),
                "course": data.get("course"),
                "award": data.get("award"),
                "image_path": data.get("image_path"),
                "seat_num": data.get("seat_num"),
                "registered": data.get("registered"),
            })

            # Validate seat number before allowing registration
            if int(seat_num) == int(data.get("seat_num", -999999)):
                if data.get("registered") is True:
                    st.info("Already registered ✅")
                else:
                    if st.button("Confirm Register", type="primary", use_container_width=True):
                        try:
                            transaction = db.transaction()
                            doc_ref = db.collection("students").document(student_id)
                            register_student_txn(transaction, doc_ref, int(seat_num))
                            st.success("Registered successfully! 🎉")
                            st.balloons()
                        except Exception as e:
                            st.error(str(e))
            else:
                st.warning("Seat number does not match. Please recheck.")
