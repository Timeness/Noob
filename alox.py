from flask import Flask, request, jsonify
import torch
from torch import nn
import numpy as np
from diffusers import DiffusionPipeline
import os
from datetime import datetime, timedelta
import random
import string

app = Flask(__name__)

# Device selection: Use GPU if available, else CPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class AloxNet(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, output_dim):
        super(AloxNet, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.transformer = nn.Transformer(embed_dim, nhead=8, num_encoder_layers=6)
        self.fc = nn.Linear(embed_dim, output_dim)
        self.softmax = nn.Softmax(dim=-1)
    
    def forward(self, x):
        embedded = self.embedding(x)
        transformed = self.transformer(embedded, embedded)
        out = self.fc(transformed[:, -1, :])
        return self.softmax(out)

vocab_size = 10000
embed_dim = 256
hidden_dim = 512
output_dim = 1024
model = AloxNet(vocab_size, embed_dim, hidden_dim, output_dim).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=0.0005)
criterion = nn.CrossEntropyLoss()

# Load diffuser model, only move to GPU if CUDA is available
diffuser = DiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5")
diffuser = diffuser.to(device)

class SyntheticDataGenerator:
    def __init__(self, vocab_size):
        self.vocab = [''.join(random.choices(string.ascii_lowercase, k=5)) for _ in range(vocab_size)]
    
    def generate_sequence(self, length=50):
        return [random.choice(self.vocab) for _ in range(length)]
    
    def generate_batch(self, batch_size=32, seq_length=50):
        sequences = [self.generate_sequence(seq_length) for _ in range(batch_size)]
        indices = [[self.vocab.index(word) for word in seq] for seq in sequences]
        return torch.tensor(indices, dtype=torch.long).to(device)

data_gen = SyntheticDataGenerator(vocab_size)

def train_model():
    model.train()
    for epoch in range(10):
        batch = data_gen.generate_batch()
        optimizer.zero_grad()
        outputs = model(batch)
        target = torch.randint(0, output_dim, (batch.shape[0],)).to(device)
        loss = criterion(outputs, target)
        loss.backward()
        optimizer.step()

def generate_text(prompt):
    model.eval()
    tokens = [random.choice(data_gen.vocab) for _ in range(5)]
    input_indices = torch.tensor([[data_gen.vocab.index(t) for t in tokens]], dtype=torch.long).to(device)
    with torch.no_grad():
        output = model(input_indices)
    top_indices = torch.topk(output, k=5, dim=-1).indices[0].cpu().numpy()
    return [data_gen.vocab[i] for i in top_indices]

def generate_code(prompt):
    tokens = generate_text(prompt)
    code_snippet = f"def alox_{tokens[0]}():\n    return '{tokens[1]}'"
    return code_snippet

last_trained = datetime.now() - timedelta(days=1)

@app.route("/api/train", methods=["POST"])
def train():
    global last_trained
    if (datetime.now() - last_trained).days >= 1:
        train_model()
        last_trained = datetime.now()
    return jsonify({"status": "Training completed"})

@app.route("/api/text", methods=["POST"])
def text():
    data = request.json
    prompt = data.get("prompt", "")
    response = ' '.join(generate_text(prompt))
    return jsonify({"response": response})

@app.route("/api/image", methods=["POST"])
def image():
    data = request.json
    prompt = data.get("prompt", "")
    image = diffuser(prompt).images[0]
    image_path = f"alox_image_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    image.save(image_path)
    return jsonify({"image_path": image_path})

@app.route("/api/code", methods=["POST"])
def code():
    data = request.json
    prompt = data.get("prompt", "")
    code_snippet = generate_code(prompt)
    return jsonify({"code": code_snippet})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
