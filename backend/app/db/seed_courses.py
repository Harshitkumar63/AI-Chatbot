"""
Authoritative Course Data Seed for Eduzyra.

=== SINGLE SOURCE OF TRUTH ===
This file seeds authoritative course information into the SQLite database.
The chatbot dynamically queries the database for all course information
(pricing, instructor, duration, syllabus, rating, etc.) rather than hardcoding.
"""

import json
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Course
from app.utils.logger import get_logger

logger = get_logger(__name__)

INITIAL_COURSES: List[Dict[str, Any]] = [
    {
        "code": "EDU-104",
        "title": "React for Products & Design Systems",
        "description": (
            "Cohort-style engineering course on building production React 19 web applications "
            "with design systems, state management, full build pipelines, and shipping to production."
        ),
        "category": "Web Development",
        "level": "Intermediate",
        "instructor": "Alex Johnson",
        "instructor_bio": "Staff Frontend Architect and creator of design systems for high-growth tech startups.",
        "duration": "8 weeks (40 hours)",
        "lessons_count": 50,
        "rating": 4.85,
        "reviews_count": 1420,
        "enrolled_students": 19600,
        "current_price": 2999.0,
        "original_price": 5999.0,
        "currency": "₹",
        "discount_percent": 50,
        "syllabus": [
            "Checkpoint 1: Enroll & Setup — Modern React 19 Architecture & Tooling",
            "Checkpoint 2: Build — Component Design Systems, Hooks & CSS Tokens",
            "Checkpoint 3: Review — State Management, Performance & Code Review with Mentors",
            "Checkpoint 4: Ship — Production Build, CI/CD Deployment & Testing",
            "Checkpoint 5: Hire-Ready — Portfolio Project & Industry Interview Prep",
        ],
        "learning_outcomes": [
            "Ship end-to-end production React applications",
            "Build scalable design systems with reusable components",
            "Pass mentor reviews at every checkpoint",
            "Master modern state management and asynchronous APIs",
        ],
        "prerequisites": ["Basic JavaScript fundamentals"],
        "is_available": True,
    },
    {
        "code": "PY-DEV",
        "title": "Python Development Masterclass",
        "description": (
            "Complete Python programming journey from absolute beginner fundamentals "
            "to building production-grade web applications, automation scripts, and REST APIs."
        ),
        "category": "Programming",
        "level": "Beginner",
        "instructor": "Dr. Rajesh Sharma",
        "instructor_bio": "Senior Python Architect with 12+ years of industry experience and author of 'Modern Python Engineering'.",
        "duration": "8 weeks (40 hours)",
        "lessons_count": 48,
        "rating": 4.9,
        "reviews_count": 1850,
        "enrolled_students": 18400,
        "current_price": 2499.0,
        "original_price": 4999.0,
        "currency": "₹",
        "discount_percent": 50,
        "syllabus": [
            "Module 1: Python Basics, Variables, Data Types & Control Flow",
            "Module 2: Data Structures (Lists, Tuples, Dictionaries, Sets)",
            "Module 3: Functions, Modules & Object-Oriented Programming (OOP)",
            "Module 4: File Handling, Error Handling & Logging",
            "Module 5: Web Scraping, BeautifulSoup & REST API Integration",
            "Module 6: Final Real-World Capstone Project & Deployment",
        ],
        "learning_outcomes": [
            "Write clean, idiomatic, and maintainable Python code",
            "Build automation tools, web scrapers, and data processors",
            "Master Object-Oriented Programming and design patterns",
            "Integrate third-party APIs and work with databases",
        ],
        "prerequisites": ["No prior programming experience required"],
        "is_available": True,
    },
    {
        "code": "ML-FOUND",
        "title": "Machine Learning Foundations & Practice",
        "description": (
            "Comprehensive machine learning course covering core mathematical concepts, "
            "supervised/unsupervised algorithms, scikit-learn, and hands-on PyTorch deep learning."
        ),
        "category": "Artificial Intelligence",
        "level": "Intermediate",
        "instructor": "Dr. Priya Mehta",
        "instructor_bio": "Ex-Google AI Researcher and PhD in Machine Learning from IIT Bombay.",
        "duration": "10 weeks (50 hours)",
        "lessons_count": 60,
        "rating": 4.8,
        "reviews_count": 1240,
        "enrolled_students": 12300,
        "current_price": 3999.0,
        "original_price": 7999.0,
        "currency": "₹",
        "discount_percent": 50,
        "syllabus": [
            "Module 1: Applied Linear Algebra & Statistics for Data Science",
            "Module 2: Data Cleaning & Feature Engineering with Pandas & NumPy",
            "Module 3: Supervised Learning (Linear/Logistic Regression, Decision Trees, SVM)",
            "Module 4: Ensemble Methods (Random Forests, Gradient Boosting, XGBoost)",
            "Module 5: Unsupervised Learning (K-Means, PCA, Hierarchical Clustering)",
            "Module 6: Neural Networks & Intro to Deep Learning with PyTorch",
        ],
        "learning_outcomes": [
            "Implement machine learning algorithms from scratch and with scikit-learn",
            "Evaluate and fine-tune models using cross-validation and hyperparameter optimization",
            "Build complete end-to-end predictive pipelines",
            "Deploy ML models using FastAPI and Docker",
        ],
        "prerequisites": ["Basic Python programming and fundamental mathematics"],
        "is_available": True,
    },
    {
        "code": "FS-WEB",
        "title": "Full-Stack Web Development Bootcamp",
        "description": (
            "Build dynamic, modern, and responsive web applications from scratch using "
            "React 19, Node.js, Express, PostgreSQL, and modern cloud deployment techniques."
        ),
        "category": "Web Development",
        "level": "Beginner",
        "instructor": "Alex Johnson",
        "instructor_bio": "Staff Full-Stack Engineer and active open-source contributor with 10+ years in web development.",
        "duration": "12 weeks (60 hours)",
        "lessons_count": 72,
        "rating": 4.9,
        "reviews_count": 2100,
        "enrolled_students": 24500,
        "current_price": 3499.0,
        "original_price": 6999.0,
        "currency": "₹",
        "discount_percent": 50,
        "syllabus": [
            "Module 1: Modern HTML5, Responsive CSS3, Flexbox & CSS Grid",
            "Module 2: JavaScript Deep Dive (ES6+, Async/Await, DOM APIs)",
            "Module 3: React 19 Frontend Engineering (Hooks, State, Routing)",
            "Module 4: Backend REST APIs with Node.js & Express",
            "Module 5: Database Design with PostgreSQL & Prisma ORM",
            "Module 6: Authentication, Security, Testing & Cloud Deployment",
        ],
        "learning_outcomes": [
            "Build responsive and interactive frontend UIs in React",
            "Architect secure and performant REST APIs in Node.js",
            "Design scalable relational database schemas",
            "Deploy full-stack web applications to cloud servers with CI/CD",
        ],
        "prerequisites": ["Basic computer literacy and enthusiasm to learn"],
        "is_available": True,
    },
    {
        "code": "DSA-PRO",
        "title": "Data Structures & Algorithms in C++ & Java",
        "description": (
            "Ace technical coding interviews at top tech companies. Master 250+ curated "
            "problems covering arrays, trees, dynamic programming, and graph algorithms."
        ),
        "category": "Computer Science",
        "level": "Beginner to Intermediate",
        "instructor": "Rohit Negi",
        "instructor_bio": "Former Microsoft SDE II and mentor to 50,000+ competitive programmers.",
        "duration": "10 weeks (55 hours)",
        "lessons_count": 80,
        "rating": 4.95,
        "reviews_count": 3400,
        "enrolled_students": 31000,
        "current_price": 2999.0,
        "original_price": 5999.0,
        "currency": "₹",
        "discount_percent": 50,
        "syllabus": [
            "Module 1: Time & Space Complexity Analysis & Bit Manipulation",
            "Module 2: Arrays, Strings, 2-Pointers & Sliding Window",
            "Module 3: Recursion, Backtracking & Divide and Conquer",
            "Module 4: Linked Lists, Stacks & Queues",
            "Module 5: Binary Trees, BSTs, Heaps & Priority Queues",
            "Module 6: Graph Algorithms (BFS, DFS, Dijkstra, Minimum Spanning Tree)",
            "Module 7: Dynamic Programming (1D, 2D, Grid DP & Knapsack Patterns)",
        ],
        "learning_outcomes": [
            "Solve medium-to-hard LeetCode problems methodically",
            "Master essential algorithmic paradigms and patterns",
            "Optimize code for time and memory constraints",
            "Excel in product company software engineering interviews",
        ],
        "prerequisites": ["Basic understanding of any language syntax (C++, Java, or Python)"],
        "is_available": True,
    },
    {
        "code": "AI-GEN",
        "title": "Generative AI & LLM Application Engineering",
        "description": (
            "Advanced masterclass on building cutting-edge Generative AI apps, multi-agent workflows, "
            "production RAG pipelines with FAISS, and fine-tuning open-source LLMs."
        ),
        "category": "Artificial Intelligence",
        "level": "Advanced",
        "instructor": "Dr. Aris Thorne",
        "instructor_bio": "AI Systems Architect and researcher specializing in large language models and neural search.",
        "duration": "8 weeks (45 hours)",
        "lessons_count": 40,
        "rating": 4.85,
        "reviews_count": 980,
        "enrolled_students": 8700,
        "current_price": 4999.0,
        "original_price": 9999.0,
        "currency": "₹",
        "discount_percent": 50,
        "syllabus": [
            "Module 1: Transformer Foundations, Tokenization & Attention Mechanisms",
            "Module 2: Prompt Engineering, Structured Outputs & Function Calling",
            "Module 3: Production RAG Architectures (Chunking, FAISS, Hybrid Search)",
            "Module 4: Autonomous Multi-Agent Workflows with LangChain & LangGraph",
            "Module 5: Fine-Tuning Open Source LLMs (LoRA, QLoRA with Llama 3 & Qwen)",
            "Module 6: LLM Evaluation, Security, Rate-Limiting & Guardrails",
        ],
        "learning_outcomes": [
            "Architect production-grade enterprise RAG systems",
            "Build autonomous agent systems with tool integration",
            "Fine-tune open-weights LLMs for specialized domain tasks",
            "Implement security guardrails and hallucination evaluation",
        ],
        "prerequisites": ["Proficiency in Python and basic machine learning concepts"],
        "is_available": True,
    },
    {
        "code": "CLOUD-DEVOPS",
        "title": "Cloud Computing & DevOps with AWS & Docker",
        "description": (
            "Learn cloud architecture, containerization, CI/CD automation, and infrastructure "
            "as code to deploy scalable and resilient applications."
        ),
        "category": "Cloud & DevOps",
        "level": "Intermediate",
        "instructor": "Michael Chang",
        "instructor_bio": "AWS Certified Solutions Architect & DevOps Lead with 11+ years managing cloud infrastructure.",
        "duration": "8 weeks (38 hours)",
        "lessons_count": 44,
        "rating": 4.75,
        "reviews_count": 850,
        "enrolled_students": 9200,
        "current_price": 3299.0,
        "original_price": 6599.0,
        "currency": "₹",
        "discount_percent": 50,
        "syllabus": [
            "Module 1: Linux Administration & Bash Automation",
            "Module 2: AWS Core Services (EC2, S3, RDS, VPC & IAM)",
            "Module 3: Docker Containerization & Multi-stage Builds",
            "Module 4: Kubernetes Orchestration & Helm Charts",
            "Module 5: Automated CI/CD Pipelines with GitHub Actions",
            "Module 6: Infrastructure as Code (IaC) with Terraform",
        ],
        "learning_outcomes": [
            "Containerize microservices with production Dockerfiles",
            "Deploy and scale containers on Kubernetes",
            "Design highly available AWS cloud infrastructures",
            "Automate delivery pipelines from commit to production",
        ],
        "prerequisites": ["Basic command line knowledge and web fundamentals"],
        "is_available": True,
    },
    {
        "code": "DATA-ANALYTICS",
        "title": "Data Analytics & Business Intelligence",
        "description": (
            "Turn raw data into actionable business insights using SQL, Python (Pandas), "
            "interactive dashboards (Power BI / Tableau), and statistical data analysis."
        ),
        "category": "Data Science",
        "level": "Beginner",
        "instructor": "Sneha Patel",
        "instructor_bio": "Principal Data Analyst with experience at top fintechs and author of practical BI frameworks.",
        "duration": "6 weeks (30 hours)",
        "lessons_count": 36,
        "rating": 4.8,
        "reviews_count": 1150,
        "enrolled_students": 14200,
        "current_price": 2799.0,
        "original_price": 5499.0,
        "currency": "₹",
        "discount_percent": 49,
        "syllabus": [
            "Module 1: Advanced Excel & Spreadsheet Modeling",
            "Module 2: SQL Fundamentals, Joins, Aggregations & Window Functions",
            "Module 3: Exploratory Data Analysis (EDA) with Python & Pandas",
            "Module 4: Data Visualization with Matplotlib & Seaborn",
            "Module 5: Interactive Executive Dashboards with Power BI & Tableau",
            "Module 6: Real-World Business Case Studies & Storytelling",
        ],
        "learning_outcomes": [
            "Write complex SQL queries to extract and transform data",
            "Perform in-depth exploratory analysis in Python",
            "Build interactive dashboards for business stakeholders",
            "Make data-driven business recommendations",
        ],
        "prerequisites": ["No prior experience required"],
        "is_available": True,
    },
    {
        "code": "CYBER-SEC",
        "title": "Cybersecurity Essentials & Ethical Hacking",
        "description": (
            "Master cybersecurity fundamentals, network defense, penetration testing methodologies, "
            "and web application vulnerability assessment (OWASP Top 10)."
        ),
        "category": "Cybersecurity",
        "level": "Beginner to Intermediate",
        "instructor": "Vikram Aditya",
        "instructor_bio": "Certified Ethical Hacker (CEH) and Security Consultant for critical infrastructure projects.",
        "duration": "8 weeks (40 hours)",
        "lessons_count": 46,
        "rating": 4.85,
        "reviews_count": 1020,
        "enrolled_students": 11100,
        "current_price": 3199.0,
        "original_price": 6399.0,
        "currency": "₹",
        "discount_percent": 50,
        "syllabus": [
            "Module 1: Network Protocols, OSI Model & Wireshark Traffic Analysis",
            "Module 2: Linux Security, Permissions & Cryptography Foundations",
            "Module 3: Web Security & OWASP Top 10 Vulnerabilities (SQLi, XSS, CSRF)",
            "Module 4: Reconnaissance, Port Scanning (Nmap) & Vulnerability Scanning",
            "Module 5: Penetration Testing Fundamentals & Metasploit",
            "Module 6: Defensive Security, Firewalls & Incident Response",
        ],
        "learning_outcomes": [
            "Identify, exploit, and remediate OWASP Top 10 vulnerabilities",
            "Perform ethical network scans and security audits",
            "Analyze and defend against cyber attacks",
            "Understand modern cryptographic systems and access controls",
        ],
        "prerequisites": ["Basic understanding of computer networks and operating systems"],
        "is_available": True,
    },
]


async def seed_courses_if_empty(session: AsyncSession) -> int:
    """
    Seed or update the database with initial authoritative courses.
    Ensures all defined courses exist in the database.
    """
    result = await session.execute(select(Course.code))
    existing_codes = set(result.scalars().all())

    count = 0
    for data in INITIAL_COURSES:
        if data["code"] not in existing_codes:
            course = Course(
                code=data["code"],
                title=data["title"],
                description=data["description"],
                category=data["category"],
                level=data["level"],
                instructor=data["instructor"],
                instructor_bio=data.get("instructor_bio"),
                duration=data["duration"],
                lessons_count=data["lessons_count"],
                rating=data["rating"],
                reviews_count=data["reviews_count"],
                enrolled_students=data["enrolled_students"],
                current_price=data["current_price"],
                original_price=data["original_price"],
                currency=data.get("currency", "₹"),
                discount_percent=data["discount_percent"],
                syllabus=json.dumps(data.get("syllabus", [])),
                learning_outcomes=json.dumps(data.get("learning_outcomes", [])),
                prerequisites=json.dumps(data.get("prerequisites", [])),
                is_available=data.get("is_available", True),
            )
            session.add(course)
            count += 1

    if count > 0:
        await session.commit()
        logger.info(f"Successfully seeded/updated {count} authoritative courses into database.")
    return count
