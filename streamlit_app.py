import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# ---------------------- Firebase init (cached) ----------------------
@st.cache_resource
def init_firebase():
    cfg = dict(st.secrets["firebase"])
    cfg["private_key"] = cfg["private_key"].replace("\\n", "\n")
    if not firebase_admin._apps:
        cred = credentials.Certificate(cfg)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# ---------------------- Helpers ----------------------
def get_student(doc_id: str):
    return db.collection("students").document(doc_id).get()

@firestore.transactional
def register_student_txn(transaction, doc_ref, expected_seat_num: int):
    snap = doc_ref.get(transaction=transaction)
    if not snap.exists:
        raise ValueError("Student not found.")

    data = snap.to_dict() or {}
    if int(data.get("seat_num", -1)) != int(expected_seat_num):
        raise ValueError("Seat number does not match our record.")
    if data.get("registered") is True:
        raise ValueError("This student is already registered.")

    transaction.update(doc_ref, {"registered": True})

# ---------------------- Session defaults ----------------------
if "candidate" not in st.session_state:
    st.session_state.candidate = None

# ---------------------- UI ----------------------
st.set_page_config(page_title="Graduation Registration", page_icon="🎓", layout="centered")
st.title("🎓 Graduation Registration")
st.caption("Enter your Student ID and Seat Number to mark yourself as registered.")

# ----- 1) Lookup form -----
with st.form("lookup_form", clear_on_submit=False):
    col1, col2 = st.columns([2, 1])
    with col1:
        student_id = st.text_input("Student ID (Document ID)", placeholder="e.g. 24WMR09274").strip()
    with col2:
        seat_num = st.number_input("Seat Number", min_value=1, step=1)
    submitted_lookup = st.form_submit_button("Lookup")

if submitted_lookup:
    if not student_id:
        st.error("Please enter a Student ID.")
        st.session_state.candidate = None
    else:
        doc = get_student(student_id)
        if not doc.exists:
            st.error("No student found with that ID.")
            st.session_state.candidate = None
        else:
            data = doc.to_dict() or {}
            if int(seat_num) != int(data.get("seat_num", -999999)):
                st.warning("Seat number does not match. Please recheck.")
                st.session_state.candidate = None
            else:
                st.session_state.candidate = {
                    "student_id": student_id,
                    "seat_num": int(seat_num),
                    "data": data,
                }

# ----- 2) Preview + confirm -----
candidate = st.session_state.candidate
if candidate:
    data = candidate["data"]

    # Pretty, minimal preview (no JSON)
    st.subheader("Record Preview")
    with st.container(border=True):
        st.markdown(
            f"**Name:** {data.get('name', '-')}\n\n"
            f"**Course:** {data.get('course', '-')}\n\n"
            f"**Award:** {data.get('award', '-')}"
        )

    if data.get("registered") is True:
        st.info("Already registered ✅")
    else:
        with st.form("confirm_form"):
            confirm = st.form_submit_button("Confirm Register", type="primary", use_container_width=True)
        if confirm:
            try:
                transaction = db.transaction()
                doc_ref = db.collection("students").document(candidate["student_id"])
                register_student_txn(transaction, doc_ref, candidate["seat_num"])
                st.success("Registered successfully! 🎉")
                st.balloons()

                # Refresh preview with updated data
                refreshed = doc_ref.get().to_dict() or {}
                st.session_state.candidate["data"] = refreshed
                st.rerun()
            except Exception as e:
                st.error(str(e))
