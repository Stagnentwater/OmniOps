FROM ollama/ollama:latest

# Start the ollama server in the background, wait for it to initialize, then pull the model
RUN nohup bash -c "ollama serve &" && sleep 5 && ollama pull llama3.2
