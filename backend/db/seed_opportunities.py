"""
Seed realistic Indian ML/AI internship opportunities into the database.
Run: python -m db.seed_opportunities
"""
import asyncio
import sys
from pathlib import Path

# Allow running from backend/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models.db import Opportunity
from app.services import embedding_service

OPPORTUNITIES = [
    {
        "title": "Machine Learning Intern",
        "company": "Sarvam AI",
        "location": "Bangalore, India",
        "description": "Work on fine-tuning and evaluating LLMs for Indian languages. Build evaluation pipelines, contribute to production inference systems, and help improve multilingual models.",
        "required_skills": ["Python", "PyTorch", "LLMs", "Fine-tuning", "HuggingFace", "CUDA"],
        "type": "internship",
        "stipend": "₹60,000/month",
        "deadline": "2026-07-31",
        "url": "https://sarvam.ai/careers",
    },
    {
        "title": "AI Research Intern",
        "company": "Krutrim",
        "location": "Bangalore, India",
        "description": "Research and develop next-gen LLM capabilities for Indian languages. Focus areas include pre-training, RLHF, and multilingual NLP.",
        "required_skills": ["Python", "PyTorch", "NLP", "Research", "LLMs", "RLHF"],
        "type": "internship",
        "stipend": "₹80,000/month",
        "deadline": "2026-08-15",
        "url": "https://olakrutrim.com/careers",
    },
    {
        "title": "ML Engineer Intern",
        "company": "Glean",
        "location": "Remote / Bangalore",
        "description": "Build semantic search and retrieval systems. Work with embeddings, vector databases, and ranking algorithms at scale.",
        "required_skills": ["Python", "Embeddings", "Vector DBs", "Elasticsearch", "FastAPI", "RAG"],
        "type": "internship",
        "stipend": "$3,000/month",
        "deadline": "2026-07-15",
        "url": "https://glean.com/careers",
    },
    {
        "title": "MLOps Intern",
        "company": "Fractal Analytics",
        "location": "Mumbai / Pune, India",
        "description": "Design and implement ML pipelines, model monitoring, and deployment infrastructure. Experience with cloud platforms and containerization preferred.",
        "required_skills": ["Python", "Docker", "Kubernetes", "MLflow", "GCP", "CI/CD", "FastAPI"],
        "type": "internship",
        "stipend": "₹45,000/month",
        "deadline": "2026-09-01",
        "url": "https://fractal.ai/careers",
    },
    {
        "title": "Data Science Intern",
        "company": "Tiger Analytics",
        "location": "Chennai / Bangalore",
        "description": "Work on forecasting models, causal inference experiments, and recommendation systems for Fortune 500 clients.",
        "required_skills": ["Python", "Scikit-learn", "Pandas", "SQL", "Statistics", "Time Series", "Causal Inference"],
        "type": "internship",
        "stipend": "₹40,000/month",
        "deadline": "2026-08-30",
        "url": "https://tigeranalytics.com/careers",
    },
    {
        "title": "Recommender Systems Intern",
        "company": "Meesho",
        "location": "Bangalore, India",
        "description": "Build and improve product recommendation algorithms. Work on collaborative filtering, neural rankers, and A/B experimentation at scale.",
        "required_skills": ["Python", "PyTorch", "Recommender Systems", "Collaborative Filtering", "Spark", "SQL"],
        "type": "internship",
        "stipend": "₹70,000/month",
        "deadline": "2026-07-20",
        "url": "https://meesho.io/careers",
    },
    {
        "title": "NLP Research Intern",
        "company": "AI4Bharat (IIT Madras)",
        "location": "Chennai, India (On-site)",
        "description": "Contribute to open-source NLP tools for Indian languages. Work on ASR, MT, and language model pre-training.",
        "required_skills": ["Python", "PyTorch", "NLP", "HuggingFace", "Research", "Transformers"],
        "type": "research",
        "stipend": "₹25,000/month",
        "deadline": "2026-08-01",
        "url": "https://ai4bharat.iitm.ac.in",
    },
    {
        "title": "Computer Vision Intern",
        "company": "Ather Energy",
        "location": "Bangalore, India",
        "description": "Develop perception algorithms for electric two-wheelers. Work on object detection, depth estimation, and edge deployment with ONNX/TensorRT.",
        "required_skills": ["Python", "OpenCV", "PyTorch", "ONNX", "TensorRT", "Object Detection", "CUDA"],
        "type": "internship",
        "stipend": "₹50,000/month",
        "deadline": "2026-07-31",
        "url": "https://atherenergy.com/careers",
    },
    {
        "title": "Generative AI Intern",
        "company": "Quantiphi",
        "location": "Mumbai / Remote",
        "description": "Build production-grade RAG systems, LLM agents, and evaluation pipelines for enterprise clients on AWS and GCP.",
        "required_skills": ["Python", "LangChain", "RAG", "LLMs", "AWS", "GCP", "Vector DBs", "FastAPI"],
        "type": "internship",
        "stipend": "₹55,000/month",
        "deadline": "2026-09-15",
        "url": "https://quantiphi.com/careers",
    },
    {
        "title": "ML Research Fellow",
        "company": "Microsoft Research India",
        "location": "Bangalore, India",
        "description": "6-month research fellowship. Work directly with researchers on NLP, fairness in ML, or systems for ML. Publish-quality research expected.",
        "required_skills": ["Python", "PyTorch", "Research", "Deep Learning", "NLP", "Statistics", "Paper Writing"],
        "type": "fellowship",
        "stipend": "₹1,00,000/month",
        "deadline": "2026-06-30",
        "url": "https://www.microsoft.com/en-us/research/lab/microsoft-research-india/",
    },
    {
        "title": "AI Infrastructure Intern",
        "company": "Sprinklr",
        "location": "Gurugram / Remote",
        "description": "Work on distributed training infrastructure, model serving optimization, and GPU cluster management.",
        "required_skills": ["Python", "CUDA", "PyTorch", "Distributed Training", "Docker", "Kubernetes"],
        "type": "internship",
        "stipend": "₹65,000/month",
        "deadline": "2026-08-31",
        "url": "https://sprinklr.com/careers",
    },
    {
        "title": "Agentic AI Intern",
        "company": "yellow.ai",
        "location": "Bangalore, India",
        "description": "Build multi-agent conversational AI systems. Work with LangGraph, tool use, memory systems, and evaluation frameworks.",
        "required_skills": ["Python", "LangGraph", "LangChain", "LLMs", "Agents", "FastAPI", "RAG"],
        "type": "internship",
        "stipend": "₹50,000/month",
        "deadline": "2026-08-15",
        "url": "https://yellow.ai/careers",
    },
    {
        "title": "SWE Intern (ML Platform)",
        "company": "Flipkart",
        "location": "Bangalore, India",
        "description": "Build internal ML platform tooling: feature stores, experiment tracking, and model registry. Scale to millions of models.",
        "required_skills": ["Python", "Go", "Spark", "Kafka", "MLflow", "SQL", "System Design"],
        "type": "internship",
        "stipend": "₹80,000/month",
        "deadline": "2026-07-15",
        "url": "https://flipkartcareers.com",
    },
    {
        "title": "Smart India Hackathon 2026",
        "company": "Ministry of Education (Govt of India)",
        "location": "Multiple Cities",
        "description": "36-hour national hackathon solving real government problems. Team of 6. Prize pool ₹1 lakh per problem statement.",
        "required_skills": ["Python", "ML", "Web Development", "Problem Solving", "Team Collaboration"],
        "type": "hackathon",
        "stipend": "₹1,00,000 prize",
        "deadline": "2026-08-31",
        "url": "https://sih.gov.in",
    },
    {
        "title": "Google Summer of Code 2026",
        "company": "Google / Open Source",
        "location": "Remote",
        "description": "3-month open source contribution program. Work with ML orgs like TensorFlow, JAX, HuggingFace. Stipend varies by country.",
        "required_skills": ["Python", "Open Source", "Git", "ML", "Documentation", "Communication"],
        "type": "fellowship",
        "stipend": "$1,500 – $3,300",
        "deadline": "2026-04-02",
        "url": "https://summerofcode.withgoogle.com",
    },
    {
        "title": "Research Intern — Evaluation & Safety",
        "company": "Anthropic",
        "location": "Remote / San Francisco",
        "description": "Work on evaluating frontier AI models. Build evals, red-team models, and develop automated safety testing pipelines.",
        "required_skills": ["Python", "LLMs", "Evaluation", "Statistical Analysis", "Research", "RAGAS"],
        "type": "internship",
        "stipend": "$8,000/month",
        "deadline": "2026-09-01",
        "url": "https://anthropic.com/careers",
    },
    {
        "title": "ML Intern — Search Ranking",
        "company": "Swiggy",
        "location": "Bangalore, India",
        "description": "Improve food search and discovery ranking. Work on LTR models, bandit algorithms, and real-time personalization.",
        "required_skills": ["Python", "LightGBM", "LTR", "Bandit Algorithms", "SQL", "Spark", "A/B Testing"],
        "type": "internship",
        "stipend": "₹60,000/month",
        "deadline": "2026-07-31",
        "url": "https://swiggy.com/careers",
    },
    {
        "title": "AI Research Intern",
        "company": "Adobe India",
        "location": "Noida / Bangalore",
        "description": "Research generative AI for creative applications: image generation, style transfer, content-aware editing. Publish at top venues.",
        "required_skills": ["Python", "PyTorch", "Diffusion Models", "GANs", "Computer Vision", "Research"],
        "type": "internship",
        "stipend": "₹75,000/month",
        "deadline": "2026-08-31",
        "url": "https://adobe.com/careers",
    },
    {
        "title": "ML Intern — Risk & Fraud",
        "company": "Razorpay",
        "location": "Bangalore, India",
        "description": "Build real-time fraud detection models. Work on graph neural networks, anomaly detection, and high-throughput model serving.",
        "required_skills": ["Python", "GNNs", "Anomaly Detection", "Scikit-learn", "Kafka", "Redis", "SQL"],
        "type": "internship",
        "stipend": "₹65,000/month",
        "deadline": "2026-08-01",
        "url": "https://razorpay.com/jobs",
    },
    {
        "title": "Kaggle Grandmaster Fellowship",
        "company": "Kaggle / Google",
        "location": "Remote",
        "description": "Competitive ML fellowship for top Kaggle competitors. Work on real ML problems, access premium compute, mentorship from Googlers.",
        "required_skills": ["Python", "XGBoost", "Deep Learning", "Feature Engineering", "Kaggle", "EDA"],
        "type": "fellowship",
        "stipend": "$2,000/month",
        "deadline": "2026-10-01",
        "url": "https://kaggle.com/competitions",
    },
]


async def seed():
    await init_db()
    async with AsyncSessionLocal() as db:
        for opp_data in OPPORTUNITIES:
            # Build embedding
            embed_text = f"{opp_data['title']} {opp_data['company']} {' '.join(opp_data['required_skills'])} {opp_data.get('description', '')}"
            embedding = await embedding_service.embed(embed_text)

            opp = Opportunity(**opp_data, embedding=embedding)
            db.add(opp)

        await db.commit()
        print(f"Seeded {len(OPPORTUNITIES)} opportunities.")


if __name__ == "__main__":
    asyncio.run(seed())
