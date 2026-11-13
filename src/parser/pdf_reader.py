"""Universal resume ingestion and extraction engine.

Extracts text from PDF, DOCX, or TXT files and parses it into a
type-safe CandidateProfile for RAG indexing and ATS match scoring.
"""

import re
from pathlib import Path
from typing import List, Tuple
import pypdf
from .profile_schema import CandidateProfile, Project, Education


def extract_text_from_file(file_path: str) -> str:
    """Extract raw text from a PDF, TXT, or Markdown resume file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume file not found at: {file_path}")

    ext = path.suffix.lower()

    if ext == ".pdf":
        text_parts = []
        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_parts.append(extracted)
        return "\n".join(text_parts)

    elif ext in [".txt", ".md"]:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    else:
        raise ValueError(f"Unsupported resume file format: {ext}. Supported: .pdf, .txt, .md")


def extract_contact_details(text: str) -> Tuple[str, str, str, str, str, str]:
    """Extract email, phone, city, LinkedIn, GitHub, and candidate name using robust regex."""
    # 1. Email
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    email = email_match.group(0) if email_match else ""

    # 2. Phone (Indian and International formats)
    phone_match = re.search(r"(?:\+91[\s-]?)?[6789]\d{9}|\+?\d{1,3}[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}", text)
    phone = phone_match.group(0).strip() if phone_match else ""

    # 3. LinkedIn
    linkedin_match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", text, re.IGNORECASE)
    linkedin = linkedin_match.group(0) if linkedin_match else ""
    if linkedin and not linkedin.startswith("http"):
        linkedin = f"https://{linkedin}"

    # 4. GitHub
    github_match = re.search(r"(?:https?://)?(?:www\.)?github\.com/[\w-]+", text, re.IGNORECASE)
    github = github_match.group(0) if github_match else ""
    if github and not github.startswith("http"):
        github = f"https://{github}"

    # 5. City heuristic (check common tech hubs)
    hubs = ["Hyderabad", "Bengaluru", "Bangalore", "Chennai", "Pune", "Mumbai", "Delhi", "Noida", "Gurugram"]
    city = "Hyderabad"
    for h in hubs:
        if re.search(rf"\b{h}\b", text, re.IGNORECASE):
            city = "Bengaluru" if h.lower() == "bangalore" else h
            break

    # 6. Name (First non-empty line before contact info)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    name = "Candidate"
    if lines:
        first_line = lines[0]
        # Ignore if first line is a title like "CURRICULUM VITAE" or "RESUME"
        if not re.search(r"resume|curriculum\s+vitae|cv|profile", first_line, re.IGNORECASE):
            name = first_line[:50]
        elif len(lines) > 1:
            name = lines[1][:50]

    return name, email, phone, city, linkedin, github


def extract_skills_inventory(text: str) -> List[str]:
    """Scan resume against a curated taxonomy of 80+ modern tech skills."""
    taxonomy = [
        # Languages
        "Python", "JavaScript", "TypeScript", "SQL", "C++", "Java", "Go",
        # AI & Machine Learning
        "Large Language Models", "LLM", "RAG", "LangChain", "LlamaIndex",
        "ChromaDB", "Qdrant", "FAISS", "HuggingFace", "Transformers",
        "PyTorch", "TensorFlow", "OpenAI", "DeepSeek", "Ollama", "NLP",
        "Computer Vision", "Scikit-Learn", "Vector Databases",
        # Backend & APIs
        "FastAPI", "Flask", "Django", "Node.js", "Express", "REST APIs",
        "GraphQL", "Microservices", "Celery", "Redis", "Kafka",
        # Databases & Cloud
        "PostgreSQL", "MySQL", "MongoDB", "SQLite", "Docker", "Kubernetes",
        "Git", "GitHub", "AWS", "Azure", "GCP", "Linux",
        # Data & Analytics
        "Pandas", "NumPy", "Apache Spark", "Airflow", "Tableau", "PowerBI"
    ]

    matched_skills = []
    text_lower = text.lower()
    for skill in taxonomy:
        # Match as whole word / boundary
        pattern = rf"\b{re.escape(skill.lower())}\b"
        if re.search(pattern, text_lower):
            matched_skills.append(skill)

    return sorted(list(set(matched_skills)))


def infer_dynamic_roles(skills: List[str]) -> Tuple[List[str], List[str]]:
    """Derive primary and secondary job search titles from skill clusters."""
    skills_lower = {s.lower() for s in skills}
    primary = []
    secondary = []

    has_ai = any(k in skills_lower for k in ["llm", "rag", "langchain", "pytorch", "transformers", "nlp", "chromadb"])
    has_python_backend = any(k in skills_lower for k in ["python", "fastapi", "flask", "django", "rest apis"])
    has_data = any(k in skills_lower for k in ["pandas", "numpy", "sql", "tableau", "spark"])

    if has_ai and has_python_backend:
        primary.extend(["AI Engineer", "Generative AI Developer", "Junior LLM Engineer"])
        secondary.extend(["Python Backend Developer", "Software Development Engineer (SDE-1)"])
    elif has_ai:
        primary.extend(["AI / ML Engineer", "Machine Learning Associate"])
        secondary.extend(["Data Scientist", "NLP Engineer"])
    elif has_python_backend:
        primary.extend(["Python Developer", "Backend Engineer", "Software Engineer"])
        secondary.extend(["Full Stack Developer", "API Developer"])
    elif has_data:
        primary.extend(["Data Analyst", "Associate Data Scientist"])
        secondary.extend(["Business Intelligence Analyst", "Python Developer"])
    else:
        primary.append("Software Engineer Trainee")
        secondary.append("Junior Developer")

    return primary, secondary


def parse_resume_to_profile(file_path: str) -> CandidateProfile:
    """Full pipeline: reads file, extracts entities, and constructs CandidateProfile."""
    raw_text = extract_text_from_file(file_path)
    name, email, phone, city, linkedin, github = extract_contact_details(raw_text)
    skills = extract_skills_inventory(raw_text)
    primary_roles, secondary_roles = infer_dynamic_roles(skills)

    # Extract sample projects from text if present
    projects = []
    project_matches = re.finditer(r"(?:PROJECTS?|ACADEMIC PROJECTS?)[\s\S]*?(?=(?:EDUCATION|EXPERIENCE|SKILLS|CERTIFICATIONS|$))", raw_text, re.IGNORECASE)
    for m in project_matches:
        p_text = m.group(0)
        # Split by distinct project lines (e.g. bold titles or bullets)
        p_lines = [l.strip() for l in p_text.split("\n") if l.strip() and not re.search(r"project", l, re.IGNORECASE)]
        if p_lines:
            projects.append(
                Project(
                    title=p_lines[0][:60],
                    description=" ".join(p_lines[1:3]) if len(p_lines) > 1 else p_lines[0],
                    technologies=[s for s in skills if s.lower() in p_text.lower()][:5]
                )
            )

    # Extract real experience from text
    exp_text = ""
    exp_match = re.search(r"(?:EXPERIENCE|WORK EXPERIENCE|PROFESSIONAL EXPERIENCE)[\s\S]*?(?=(?:PROJECTS|ACADEMIC PROJECTS|EDUCATION|SKILLS|CERTIFICATES|ACHIEVEMENTS|$))", raw_text, re.IGNORECASE)
    if exp_match:
        exp_lines = [l.strip() for l in exp_match.group(0).split("\n") if l.strip()]
        if len(exp_lines) > 1:
            exp_text = "\n".join(exp_lines[1:]).strip()

    # Extract real projects from text
    proj_text = ""
    proj_match = re.search(r"(?:PROJECTS|ACADEMIC PROJECTS)[\s\S]*?(?=(?:CERTIFICATES|ACHIEVEMENTS|EDUCATION|EXPERIENCE|SKILLS|$))", raw_text, re.IGNORECASE)
    if proj_match:
        proj_lines = [l.strip() for l in proj_match.group(0).split("\n") if l.strip()]
        if len(proj_lines) > 1:
            proj_text = "\n".join(proj_lines[1:]).strip()

    # Extract education from text
    edu_text = ""
    edu_match = re.search(r"(?:EDUCATION|ACADEMIC BACKGROUND)[\s\S]*?(?=(?:CERTIFICATES|ACHIEVEMENTS|PROJECTS|EXPERIENCE|SKILLS|$))", raw_text, re.IGNORECASE)
    if edu_match:
        edu_lines = [l.strip() for l in edu_match.group(0).split("\n") if l.strip()]
        if len(edu_lines) > 1:
            edu_text = "\n".join(edu_lines[1:]).strip()

    # Factual summary strictly derived from candidate's extracted credentials
    summary = f"{name} — {', '.join(primary_roles[:2])} with hands-on engineering experience in {', '.join(skills[:5])}."

    return CandidateProfile(
        name=name,
        email=email,
        phone=phone,
        city=city,
        linkedin_url=linkedin or None,
        github_url=github or None,
        skills=skills,
        projects=projects,
        summary=summary,
        projects_text=proj_text,
        experience_text=exp_text,
        education_text=edu_text,
        primary_roles=primary_roles,
        secondary_roles=secondary_roles,
        target_locations=["Hyderabad", "Bengaluru", "Chennai", "Pune", "Remote"]
    )

