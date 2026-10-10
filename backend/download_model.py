import os
from sentence_transformers import SentenceTransformer

def main():
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    primary_path = os.path.join(base_dir, "models", "all-MiniLM-L6-v2")
    legacy_path = os.path.join(base_dir, "models", "embedding_model")
    
    print(f"Loading/Exporting '{model_name}'...")
    
    # Load model (from cache if already downloaded)
    model = SentenceTransformer(model_name)
    
    print(f"Saving model locally to: {primary_path}")
    model.save(primary_path)
    
    # Also verify offline loading with local_files_only
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    offline_model = SentenceTransformer(primary_path, local_files_only=True)
    test_dim = len(offline_model.encode(["OmniOps air-gapped test"])[0])
    print(f"Verified offline loading! Vector dimensionality: {test_dim}")
    print("\nModel successfully prepared for air-gapped on-premise execution!")

if __name__ == "__main__":
    main()
