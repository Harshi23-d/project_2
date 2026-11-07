import json
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
STORE_FILE = DATA_DIR / "huddle_store.json"


def ensure_store() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not STORE_FILE.exists():
        STORE_FILE.write_text(
            json.dumps({"users": {}, "requests": [], "messages": {}}, indent=2),
            encoding="utf-8",
        )


def load_store() -> dict:
    ensure_store()
    with STORE_FILE.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {"users": {}, "requests": [], "messages": {}}
    data.setdefault("users", {})
    data.setdefault("requests", [])
    data.setdefault("messages", {})
    return data


def save_store(data: dict) -> None:
    ensure_store()
    with STORE_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def normalize_username(value: str) -> str:
    return value.strip().lower().replace("@", "")


def pair_key(user_a: str, user_b: str) -> str:
    return "|".join(sorted([user_a, user_b]))


def get_friends(username: str, store: dict) -> list[str]:
    accepted = []
    for req in store["requests"]:
        if req.get("status") != "accepted":
            continue
        if req.get("from") == username:
            accepted.append(req.get("to"))
        elif req.get("to") == username:
            accepted.append(req.get("from"))
    return sorted(set(accepted))


def get_requests_for(username: str, store: dict) -> list[dict]:
    return [
        req for req in store["requests"] if req.get("to") == username and req.get("status") == "pending"
    ]


def get_messages(username_a: str, username_b: str, store: dict) -> list[dict]:
    return store["messages"].get(pair_key(username_a, username_b), [])


st.set_page_config(page_title="Huddle", page_icon="💬", layout="wide")

if "current_user" not in st.session_state:
    st.session_state.current_user = None

if st.session_state.current_user is None:
    st.title("Huddle")
    st.caption("A simple private messenger without Firebase.")

    tab1, tab2 = st.tabs(["Login", "Create account"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
            if submitted:
                store = load_store()
                match = None
                for user in store["users"].values():
                    if user.get("email", "").lower() == email.strip().lower() and user.get("password") == password:
                        match = user
                        break
                if match:
                    st.session_state.current_user = match["username"]
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

    with tab2:
        with st.form("signup_form"):
            name = st.text_input("Display name")
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Create account")
            if submitted:
                store = load_store()
                cleaned_username = normalize_username(username)
                cleaned_email = email.strip().lower()
                if len(name.strip()) < 2:
                    st.error("Display name must be at least 2 characters.")
                elif len(cleaned_username) < 3:
                    st.error("Username must be at least 3 characters.")
                elif any(user["username"].lower() == cleaned_username for user in store["users"].values()):
                    st.error("That username is already taken.")
                elif any(user["email"].lower() == cleaned_email for user in store["users"].values()):
                    st.error("That email is already registered.")
                else:
                    store["users"][cleaned_username] = {
                        "username": cleaned_username,
                        "display_name": name.strip(),
                        "email": cleaned_email,
                        "password": password,
                    }
                    save_store(store)
                    st.success("Account created. Sign in now.")
                    st.session_state.current_user = cleaned_username
                    st.rerun()
    st.stop()

username = st.session_state.current_user
store = load_store()
user = store["users"].get(username)
if user is None:
    st.error("Session expired.")
    st.session_state.current_user = None
    st.stop()

friends = get_friends(username, store)
requests = [req for req in store["requests"] if req.get("to") == username and req.get("status") == "pending"]
selected_friend = st.session_state.get("selected_friend")
if selected_friend not in friends:
    selected_friend = friends[0] if friends else None
st.session_state.selected_friend = selected_friend

st.sidebar.title(f"Hi, {user['display_name']}")
st.sidebar.caption(f"@{username}")
if st.sidebar.button("Log out"):
    st.session_state.current_user = None
    st.rerun()

st.sidebar.subheader("Friends")
search_term = st.sidebar.text_input("Search username")
for friend in [f for f in friends if search_term.lower() in f.lower()]:
    if st.sidebar.button(friend, key=f"friend_{friend}"):
        st.session_state.selected_friend = friend
        st.rerun()

if not friends:
    st.sidebar.info("No friends yet.")

st.sidebar.subheader("Requests")
if requests:
    for req in requests:
        sender = req["from"]
        col1, col2 = st.sidebar.columns(2)
        col1.caption(sender)
        if col1.button("Accept", key=f"accept_{sender}"):
            for item in store["requests"]:
                if item.get("from") == sender and item.get("to") == username and item.get("status") == "pending":
                    item["status"] = "accepted"
                    break
            save_store(store)
            st.rerun()
        if col2.button("Reject", key=f"reject_{sender}"):
            store["requests"] = [
                r for r in store["requests"] if not (r.get("from") == sender and r.get("to") == username and r.get("status") == "pending")
            ]
            save_store(store)
            st.rerun()
else:
    st.sidebar.caption("No pending invites.")

st.sidebar.subheader("Find people")
friend_username = st.sidebar.text_input("Username to add")
if st.sidebar.button("Send request"):
    target_username = normalize_username(friend_username)
    if target_username == username:
        st.sidebar.error("You cannot add yourself.")
    elif target_username not in store["users"]:
        st.sidebar.error("User not found.")
    else:
        already = any(
            (req.get("from") == username and req.get("to") == target_username)
            or (req.get("from") == target_username and req.get("to") == username)
            for req in store["requests"]
        )
        if already:
            st.sidebar.warning("A connection already exists.")
        else:
            store["requests"].append({"from": username, "to": target_username, "status": "pending"})
            save_store(store)
            st.sidebar.success("Request sent.")

st.title("Private messages")
if not friends:
    st.info("No accepted friends yet. Add someone from the sidebar to start chatting.")
    st.stop()

friend = selected_friend or friends[0]
st.subheader(f"Chat with {friend}")
messages = get_messages(username, friend, store)

for msg in messages:
    sender = msg["sender"]
    if sender == username:
        st.markdown(
            f"<div style='text-align: right; background: #1f7a8c; color: white; padding: 0.75rem; border-radius: 0.75rem; width: fit-content; margin-left: auto; margin-bottom: 0.5rem;'>"
            f"{msg['text']}"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='text-align: left; background: #eaf2f8; color: #1a1a1a; padding: 0.75rem; border-radius: 0.75rem; width: fit-content; margin-bottom: 0.5rem;'>"
            f"{msg['text']}"
            f"</div>",
            unsafe_allow_html=True,
        )

with st.form(key="chat_form"):
    message_text = st.text_area("Message", height=100)
    sent = st.form_submit_button("Send")
    if sent and message_text.strip():
        key = pair_key(username, friend)
        store["messages"].setdefault(key, [])
        store["messages"][key].append({"sender": username, "text": message_text.strip()})
        save_store(store)
        st.rerun()

st.caption("This version stores members and messages in a local JSON file so it can run on Streamlit without Firebase.")
