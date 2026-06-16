import os
import logging
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    'DB_CONN_URI',
    'postgresql://postgres:@localhost:5432/ai_assistant'
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class ScrapedJob(Base):
    __tablename__ = 'scraped_jobs'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    site         = Column(String(50), nullable=False)
    title        = Column(Text)
    company      = Column(Text)
    job_url      = Column(Text, unique=True)
    location     = Column(Text)
    description  = Column(Text)
    job_type     = Column(Text)
    compensation = Column(Text)
    date_posted  = Column(Date)
    expires      = Column(Date)
    category     = Column(Text)
    remote       = Column(Text)
    scraped_at   = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Create tables if they don't exist."""
    Base.metadata.create_all(engine)
    logger.info("Database tables initialised.")


def get_session():
    return SessionLocal()


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def insert_jobs(jobs_list):
    """Insert a list of job dicts into scraped_jobs. Skips duplicates by job_url."""
    if not jobs_list:
        return 0

    session = get_session()
    count = 0
    try:
        for job in jobs_list:
            url = job.get('job_url')
            if url:
                existing = session.query(ScrapedJob).filter(
                    ScrapedJob.job_url == url
                ).first()
                if existing:
                    continue

            db_job = ScrapedJob(
                site=job.get('site'),
                title=job.get('title'),
                company=job.get('company'),
                job_url=job.get('job_url'),
                location=job.get('location'),
                description=job.get('description'),
                job_type=job.get('job_type'),
                compensation=job.get('compensation'),
                date_posted=_parse_date(job.get('date_posted')),
                expires=_parse_date(job.get('expires')),
                category=job.get('category'),
                remote=job.get('remote'),
                scraped_at=datetime.utcnow(),
            )
            session.add(db_job)
            count += 1

        session.commit()
        logger.info("Inserted %d new job(s) into database.", count)
    except Exception as e:
        session.rollback()
        logger.error("Database insert failed: %s", e)
        raise
    finally:
        session.close()

    return count
