import os
from sentence_transformers import SentenceTransformer

def main():
    model_name = "BAAI/bge-m3"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(base_dir, "models", "embedding_model")
    
    print(f"Downloading/Loading '{model_name}'...")
    print("This might take a few minutes if it hasn't been cached yet.")
    
    # This will download the model or load it from the HuggingFace cache
    model = SentenceTransformer(model_name)
    
    print(f"Saving model locally to: {save_path}")
    model.save(save_path)
    print("\nModel successfully saved locally!")
    print("You can now update your .env file to use this local path:")
    print('EMBEDDING_MODEL_NAME="./models/embedding_model"')

if __name__ == "__main__":
    main()
