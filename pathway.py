import os
import re
import tempfile
import streamlit as st

# LangChain + Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate

# ReportLab for PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Email (SMTP)
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders


# ==========================
# CONFIG: REPLACE THESE
# ==========================
GEMINI_API_KEY   = "AIzaSyDnJ0Lcz34TLNm5_l3OAJN_kviwkictfjc"     # <-- Replace with your Gemini key
EMAIL_ADDRESS    = "jeevikar2005@gmail.com"         # <-- Replace with your Gmail
EMAIL_PASSWORD   = "iakg zbtn rjos gvat"    # <-- Replace with your Gmail App Password


# ==========================
# STREAMLIT UI
# ==========================
st.set_page_config(page_title="Learning Pathway Generator", page_icon="📚")
st.title("📚 Automatic Learning Pathway Generator")
st.write("Fill the form, get a personalized pathway as **PDF** and receive it by **email**.")

with st.form("pathway_form"):
    learner_name = st.text_input("Your Name")
    course = st.text_input("Course / Topic (e.g., Data Science, Web Dev)")
    duration = st.text_input("Preferred Duration (e.g., 8 weeks, 3 months)")
    level = st.selectbox("Current Skill Level", ["Beginner", "Intermediate", "Advanced"])
    goals = st.text_area("Your Learning Goals (short bullets are fine)")
    recipient_email = st.text_input("Your Email (to receive the PDF)")
    submitted = st.form_submit_button("Generate & Send PDF")


# ==========================
# LLM: Generate Pathway
# ==========================
def generate_learning_pathway(course: str, duration: str, level: str, goals: str) -> str:
    """
    Uses Gemini 1.5 via LangChain to produce a well-structured learning pathway.
    NOTE: Use the new 'models/...' naming to avoid 404 errors.
    """
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.0-flash",   # or "models/gemini-1.5-pro"
        google_api_key=GEMINI_API_KEY,
        temperature=0.6,
    )

    prompt = PromptTemplate(
        input_variables=["course", "duration", "level", "goals"],
        template=(
            "You are an expert curriculum designer. Create a highly practical, step-by-step "
            "learning pathway for the course/topic: '{course}'.\n"
            "Learner current level: {level}\n"
            "Planned total duration: {duration}\n"
            "Learner goals: {goals}\n\n"
            "Output requirements (plain text only — no HTML tags):\n"
            "1) Short intro\n"
            "2) Weekly breakdown with outcomes (Week 1, Week 2, ...)\n"
            "3) Key topics & must-learn concepts\n"
            "4) Hands-on projects (at least 2) with brief briefs\n"
            "5) Recommended resources (max 6) with one-line why\n"
            "6) Assessment & milestones\n"
            "7) Tips to stay consistent\n"
            "Keep it concise, skimmable, and actionable."
        ),
    )

    chain = prompt | llm
    result = chain.invoke(
        {"course": course, "duration": duration, "level": level, "goals": goals}
    )
    # ChatGoogleGenerativeAI returns an object with .content
    return result.content if hasattr(result, "content") else str(result)


# ==========================
# PDF: Safe Text Cleaning
# ==========================
def clean_text_for_pdf(text: str) -> str:
    """
    ReportLab Paragraph supports a tiny subset of HTML. To avoid crashes:
    - Strip ALL HTML-like tags
    - Remove markdown backticks and asterisks
    - Normalize whitespace
    """
    text = re.sub(r"<[^>]+>", "", text)    # remove any <tags>
    text = text.replace("`", "")           # remove code backticks
    text = text.replace("**", "")          # remove bold markers
    text = text.replace("* ", "• ")        # keep nice bullets
    text = text.replace("*", "")           # leftover single asterisks
    text = re.sub(r"[ \t]+", " ", text)    # collapse spaces
    return text.strip()


def build_pdf(pathway_text: str, title: str, output_path: str) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(output_path)
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    # split on blank lines to keep logical paragraphs
    blocks = [b.strip() for b in pathway_text.split("\n")]

    for block in blocks:
        cleaned = clean_text_for_pdf(block)
        if not cleaned:
            continue
        story.append(Paragraph(cleaned, styles["Normal"]))
        story.append(Spacer(1, 8))

    doc.build(story)


# ==========================
# EMAIL: Send with PDF
# ==========================
def send_email_with_pdf(to_email: str, subject: str, body: str, pdf_path: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as f:
        attach = MIMEBase("application", "octet-stream")
        attach.set_payload(f.read())
    encoders.encode_base64(attach)
    attach.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(pdf_path)}"')
    msg.attach(attach)

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)  # <-- MUST be a Gmail App Password
    server.send_message(msg)
    server.quit()


# ==========================
# MAIN FLOW
# ==========================
if submitted:
    if not all([learner_name, course, duration, level, goals, recipient_email]):
        st.error("⚠️ Please fill all fields.")
    else:
        with st.spinner("🧠 Generating your personalized learning pathway..."):
            pathway = generate_learning_pathway(course, duration, level, goals)

        st.success("✅ Pathway generated!")
        st.text_area("Preview (plain text):", pathway, height=300)

        # Create temp PDF
        with st.spinner("📄 Creating PDF..."):
            safe_title = f"Learning Pathway — {course}"
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                pdf_path = tmp.name
            build_pdf(pathway, safe_title, pdf_path)
        st.success("✅ PDF created!")

        # Offer download
        with open(pdf_path, "rb") as pdf_file:
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf_file.read(),
                file_name=f"{learner_name.replace(' ', '_')}_{course.replace(' ', '_')}_Pathway.pdf",
                mime="application/pdf",
            )

        # Email it
        with st.spinner("📧 Sending email with PDF attachment..."):
            try:
                subject = f"Your Learning Pathway for {course}"
                body = (
                    f"Hi {learner_name},\n\n"
                    f"Please find attached your personalized learning pathway for {course}.\n\n"
                    f"All the best!\n"
                )
                send_email_with_pdf(recipient_email, subject, body, pdf_path)
                st.success(f"✅ Sent to {recipient_email}")
            except Exception as e:
                st.error(f"❌ Failed to send email: {e}")
            finally:
                # Clean temp file
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass
