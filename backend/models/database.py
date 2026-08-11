"""SQLAlchemy Database ORM models for persistent storage.

Implements persistent runs, document storage, hierarchical cluster trees,
chunks, and background job records.
"""
import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from backend.config import Config

Base = declarative_base()

# Global Engine and Session Maker
_engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


class User(Base):
    __tablename__ = 'users'

    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    plan_tier = Column(String(50), default='free')

    runs = relationship('Run', back_populates='user', cascade='all, delete-orphan')


class Run(Base):
    __tablename__ = 'runs'

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    name = Column(String(255), default='Untitled Run')
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(50), default='created')  # created, processing, completed, failed
    doc_count = Column(Integer, default=0)
    cluster_count = Column(Integer, default=0)
    mode = Column(String(50), default='classic')  # classic | semantic

    user = relationship('User', back_populates='runs')
    documents = relationship('DocumentRecord', back_populates='run', cascade='all, delete-orphan')
    clusters = relationship('ClusterRecord', back_populates='run', cascade='all, delete-orphan')
    jobs = relationship('JobRecord', back_populates='run', cascade='all, delete-orphan')


class DocumentRecord(Base):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey('runs.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    storage_path = Column(Text, nullable=False)
    mime_type = Column(String(100), default='text/plain')
    word_count = Column(Integer, default=0)
    page_count = Column(Integer, default=1)
    extraction_status = Column(String(50), default='success')
    content = Column(Text, nullable=True)

    run = relationship('Run', back_populates='documents')
    chunks = relationship('ChunkRecord', back_populates='document', cascade='all, delete-orphan')


class ChunkRecord(Base):
    __tablename__ = 'chunks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    text = Column(Text, nullable=False)
    page_number = Column(Integer, default=1)
    token_count = Column(Integer, default=0)

    document = relationship('DocumentRecord', back_populates='chunks')


class ClusterRecord(Base):
    __tablename__ = 'clusters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey('runs.id'), nullable=False)
    cluster_id = Column(Integer, nullable=False)  # fcluster 1-based index
    label = Column(String(255), default='Cluster')
    ai_summary = Column(Text, nullable=True)
    keywords_json = Column(Text, nullable=True)
    representative_document_id = Column(Integer, nullable=True)
    parent_cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=True)

    run = relationship('Run', back_populates='clusters')


class ClusterDocumentRecord(Base):
    __tablename__ = 'cluster_documents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=False)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    similarity_score = Column(Float, default=1.0)
    is_outlier = Column(Boolean, default=False)


class JobRecord(Base):
    __tablename__ = 'jobs'

    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey('runs.id'), nullable=False)
    job_type = Column(String(50), nullable=False)  # ingestion | clustering | rag
    status = Column(String(50), default='queued')  # queued | processing | completed | failed
    progress = Column(Float, default=0.0)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    run = relationship('Run', back_populates='jobs')


def init_db(db_url: str = None):
    """Initialize database tables and rebind engine if custom db_url provided."""
    global _engine, SessionLocal
    url = db_url or Config.SQLALCHEMY_DATABASE_URI
    _engine = create_engine(url, echo=False)
    Base.metadata.create_all(_engine)
    SessionLocal.configure(bind=_engine)
    return _engine, SessionLocal
