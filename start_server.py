"""
RagGita Server Startup Script
Usage: python start_server.py [--port PORT] [--host HOST] [--reload]
"""
import os
import sys
import argparse


def check_requirements():
    """Check if required packages are installed"""
    try:
        import fastapi
        import uvicorn
        import langchain
        print("All required packages found!")
        return True
    except ImportError as e:
        print(f"Missing package: {e}")
        print("\nPlease install requirements:")
        print("  pip install -r requirements.txt")
        return False


def main():
    parser = argparse.ArgumentParser(description="Start RagGita API Server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", 8000)),
        help="Port to run the server on (default: 8000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("RagGita API Server")
    print("=" * 50)
    print(f"\nConfiguration:")
    print(f"  Host:     {args.host}")
    print(f"  Port:     {args.port}")
    print(f"  Reload:   {args.reload}")
    print(f"  Workers:  {args.workers}")
    print()

    # Check requirements
    if not check_requirements():
        sys.exit(1)

    # Check if vector DB exists
    if not os.path.exists("gita_vector_db"):
        print("\nERROR: Vector database not found!")
        print("Please run ingest.py first to create the vector database:")
        print("  python ingest.py")
        sys.exit(1)

    print("\nStarting server...")
    print(f"API will be available at: http://{args.host}:{args.port}")
    print(f"Documentation: http://{args.host}:{args.port}/docs")
    print("=" * 50)
    print()

    import uvicorn
    uvicorn.run(
        "api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1
    )


if __name__ == "__main__":
    main()
