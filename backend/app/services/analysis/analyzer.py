import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models.repository import RepositoryAnalysis
from app.schemas.repository import RepositoryAnalysisRequest
from app.services.repository.validation import validate_github_url
from app.services.repository.clone import clone_repository, cleanup_workspace
from app.services.analysis.language import detect_language
from app.services.analysis.framework import detect_framework
from app.services.testing.discovery import detect_testing
from app.services.analysis.structure import analyze_structure, find_relevant_files
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

def perform_analysis(analysis_id: str, request: RepositoryAnalysisRequest):
    db: Session = SessionLocal()
    analysis_record = db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == analysis_id).first()
    if not analysis_record:
        db.close()
        return

    try:
        # 1. Validation
        url_str = validate_github_url(request.repository_url)
        # Extract name from url (last part)
        repo_name = url_str.split("/")[-1]
        
        analysis_record.status = "cloning"
        analysis_record.repository_name = repo_name
        db.commit()

        # 2. Cloning
        repo_dir = clone_repository(url_str)
        if not repo_dir:
            raise Exception("Repository could not be cloned.")

        analysis_record.status = "analyzing"
        db.commit()
        
        try:
            # 3. Language & File Count
            primary_language, file_count, estimated_loc = detect_language(repo_dir)
            analysis_record.primary_language = primary_language
            analysis_record.file_count = file_count
            analysis_record.estimated_loc = estimated_loc
            
            # 4. Framework
            if primary_language:
                framework = detect_framework(repo_dir, primary_language)
                analysis_record.framework = framework
                
            # 5. Testing
            if primary_language:
                test_framework, test_file_count = detect_testing(repo_dir, primary_language)
                analysis_record.test_framework = test_framework
                analysis_record.test_file_count = test_file_count
                
            # 6. Structure
            important_dirs, has_readme = analyze_structure(repo_dir)
            analysis_record.important_directories = important_dirs
            analysis_record.has_readme = has_readme
            
            # 7. Relevant Files
            relevant_files = find_relevant_files(repo_dir, request.bug_description or "")
            analysis_record.relevant_files = relevant_files
            
            # Finalize
            analysis_record.status = "completed"
            analysis_record.completed_at = datetime.now()
            db.commit()
            
        finally:
            # Always cleanup
            cleanup_workspace(repo_dir)

    except Exception as e:
        logger.error(f"Analysis failed for {analysis_id}: {e}")
        analysis_record.status = "failed"
        analysis_record.error_message = str(e)
        analysis_record.completed_at = datetime.now()
        db.commit()
    finally:
        db.close()
