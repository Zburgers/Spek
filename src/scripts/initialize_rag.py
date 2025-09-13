"""
Vector Database Initialization Script

This script initializes the Pinecone vector database for RAG functionality.
Run this script once when setting up RAG for the first time.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add the src directory to the path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.vector_store import vector_store_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def initialize_vector_database():
    """Initialize the vector database for RAG."""
    
    try:
        logger.info("Initializing vector database for RAG...")
        
        # Check if API key is configured
        if not settings.PINECONE_API_KEY:
            logger.error("PINECONE_API_KEY not configured. Please add it to your .env file.")
            return False
        
        # Initialize Pinecone client
        vector_store_service.initialize_client(settings.PINECONE_API_KEY.get_secret_value())
        
        # Create index if it doesn't exist
        await vector_store_service.create_index_if_not_exists(
            dimension=settings.EMBEDDING_DIMENSION
        )
        
        # Get index stats to verify setup
        stats = await vector_store_service.get_index_stats()
        logger.info(f"Vector database initialized successfully. Stats: {stats}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize vector database: {e}")
        return False


if __name__ == "__main__":
    print("RAG Vector Database Initialization")
    print("=" * 40)
    print("This script will initialize the Pinecone vector database for RAG functionality.")
    print("Make sure you have added PINECONE_API_KEY to your .env file.")
    print()
    
    # Run the initialization
    success = asyncio.run(initialize_vector_database())
    
    if success:
        print("✅ Vector database initialization completed successfully!")
        print("You can now upload documents and use RAG functionality.")
    else:
        print("❌ Vector database initialization failed.")
        print("Please check your configuration and try again.")
