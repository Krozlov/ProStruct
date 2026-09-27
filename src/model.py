"""
ProStruct Model: Small Transformer for protein sequence analysis.
Supports masked language modeling pretraining and binding-site classification.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml
from pathlib import Path
import json
from typing import Dict, List, Tuple


# Amino acid vocabulary
AA_VOCAB = {
    'A': 0, 'R': 1, 'N': 2, 'D': 3, 'C': 4,
    'E': 5, 'Q': 6, 'G': 7, 'H': 8, 'I': 9,
    'L': 10, 'K': 11, 'M': 12, 'F': 13, 'P': 14,
    'S': 15, 'T': 16, 'W': 17, 'Y': 18, 'V': 19,
    '<PAD>': 20, '<MASK>': 21, '<UNK>': 22
}

REVERSE_AA_VOCAB = {v: k for k, v in AA_VOCAB.items()}


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for sequences."""
    
    def __init__(self, d_model: int, max_len: int = 1024):
        super().__init__()
        position = torch.arange(max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-torch.log(torch.tensor(10000.0)) / d_model))
        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, :x.size(1)]


class ProteinTransformer(nn.Module):
    """Small Transformer encoder for protein sequences."""
    
    def __init__(self, config: Dict):
        super().__init__()
        self.config = config
        
        self.embedding_dim = config['embedding_dim']
        self.vocab_size = config['vocab_size']
        self.max_seq_len = config['max_seq_len']
        self.num_heads = config['num_heads']
        self.num_layers = config['num_layers']
        self.hidden_dim = config['hidden_dim']
        self.dropout = config['dropout']
        
        # Token embedding
        self.token_embedding = nn.Embedding(self.vocab_size, self.embedding_dim, padding_idx=AA_VOCAB['<PAD>'])
        
        # Positional encoding
        self.pos_encoding = PositionalEncoding(self.embedding_dim, self.max_seq_len)
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.embedding_dim,
            nhead=self.num_heads,
            dim_feedforward=self.hidden_dim,
            dropout=self.dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=self.num_layers)
        
        # MLM head (for pretraining)
        self.mlm_head = nn.Linear(self.embedding_dim, self.vocab_size)
        
        # Classification head (for binding site prediction)
        self.classification_head = nn.Linear(self.embedding_dim, 2)  # Binary: binding vs non-binding
        
        self.dropout_layer = nn.Dropout(self.dropout)
    
    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor = None) -> torch.Tensor:
        """
        Forward pass through the transformer.
        
        Args:
            input_ids: (batch_size, seq_len) token IDs
            attention_mask: (batch_size, seq_len) mask for padding (1 for real tokens, 0 for padding)
        
        Returns:
            embeddings: (batch_size, seq_len, embedding_dim)
        """
        # Token embeddings
        x = self.token_embedding(input_ids)
        
        # Positional encoding
        x = self.pos_encoding(x)
        
        # Dropout
        x = self.dropout_layer(x)
        
        # Transformer encoder
        if attention_mask is not None:
            # Convert attention mask to transformer format (0 for padding, 1 for tokens)
            src_key_padding_mask = (attention_mask == 0)
        else:
            src_key_padding_mask = None
        
        embeddings = self.transformer(x, src_key_padding_mask=src_key_padding_mask)
        
        return embeddings
    
    def forward_mlm(self, input_ids: torch.Tensor, attention_mask: torch.Tensor = None) -> torch.Tensor:
        """Forward pass for masked language modeling."""
        embeddings = self.forward(input_ids, attention_mask)
        logits = self.mlm_head(embeddings)
        return logits
    
    def forward_classification(self, input_ids: torch.Tensor, attention_mask: torch.Tensor = None) -> torch.Tensor:
        """Forward pass for binding site classification."""
        embeddings = self.forward(input_ids, attention_mask)
        logits = self.classification_head(embeddings)
        return logits


class ProStructModel:
    """Wrapper class for training and inference."""
    
    def __init__(self, config_path: str = 'config.yaml', device: str = 'cpu'):
        self.config = self.load_config(config_path)
        self.device = torch.device(device)
        
        self.model = ProteinTransformer(self.config['model']).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.config['training']['learning_rate'])
        
        self.pad_token_id = AA_VOCAB['<PAD>']
        self.mask_token_id = AA_VOCAB['<MASK>']
    
    def load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def encode_sequence(self, sequence: str) -> List[int]:
        """Convert amino acid sequence to token IDs."""
        tokens = []
        for aa in sequence:
            if aa in AA_VOCAB:
                tokens.append(AA_VOCAB[aa])
            else:
                tokens.append(AA_VOCAB['<UNK>'])
        return tokens
    
    def decode_sequence(self, token_ids: List[int]) -> str:
        """Convert token IDs to amino acid sequence."""
        sequence = []
        for tid in token_ids:
            if tid in REVERSE_AA_VOCAB:
                aa = REVERSE_AA_VOCAB[tid]
                if aa not in ['<PAD>', '<MASK>', '<UNK>']:
                    sequence.append(aa)
        return ''.join(sequence)
    
    def create_attention_mask(self, token_ids: List[int]) -> torch.Tensor:
        """Create attention mask from token IDs."""
        mask = [1 if tid != self.pad_token_id else 0 for tid in token_ids]
        return torch.tensor(mask, dtype=torch.long)
    
    def mask_tokens(self, token_ids: List[int], mask_prob: float = 0.15) -> Tuple[List[int], List[int]]:
        """
        Apply random masking for MLM pretraining.
        Returns: (masked_token_ids, labels)
        """
        masked_ids = token_ids.copy()
        labels = [-100] * len(token_ids)  # -100 is PyTorch's ignore index
        
        for i, tid in enumerate(token_ids):
            if tid == self.pad_token_id:
                continue
            if random.random() < mask_prob:
                labels[i] = tid
                # 80% mask, 10% random, 10% keep original
                rand = random.random()
                if rand < 0.8:
                    masked_ids[i] = self.mask_token_id
                elif rand < 0.9:
                    masked_ids[i] = random.randint(0, 19)  # Random amino acid
                # else keep original
        
        return masked_ids, labels
    
    def collate_batch(self, batch: List[Dict], task: str = 'mlm') -> Dict:
        """Collate a batch of sequences for training."""
        sequences = [item['sequence'] for item in batch]
        
        # Encode sequences
        token_ids_list = [self.encode_sequence(seq) for seq in sequences]
        
        # Pad sequences
        max_len = max(len(ids) for ids in token_ids_list)
        max_len = min(max_len, self.config['model']['max_seq_len'])
        
        padded_ids = []
        attention_masks = []
        
        for token_ids in token_ids_list:
            # Truncate if too long
            if len(token_ids) > max_len:
                token_ids = token_ids[:max_len]
            
            # Pad
            padded = token_ids + [self.pad_token_id] * (max_len - len(token_ids))
            padded_ids.append(padded)
            
            # Attention mask
            mask = [1 if tid != self.pad_token_id else 0 for tid in padded]
            attention_masks.append(mask)
        
        input_ids = torch.tensor(padded_ids, dtype=torch.long).to(self.device)
        attention_mask = torch.tensor(attention_masks, dtype=torch.long).to(self.device)
        
        if task == 'mlm':
            # Apply masking
            masked_ids_list = []
            labels_list = []
            for token_ids in padded_ids:
                masked, labels = self.mask_tokens(token_ids, self.config['training']['mask_prob'])
                masked_ids_list.append(masked)
                labels_list.append(labels)
            
            masked_ids = torch.tensor(masked_ids_list, dtype=torch.long).to(self.device)
            labels = torch.tensor(labels_list, dtype=torch.long).to(self.device)
            
            return {
                'input_ids': masked_ids,
                'attention_mask': attention_mask,
                'labels': labels.item() if labels.dim() == 0 else labels
            }
        
        elif task == 'classification':
            # Create binding site labels
            binding_labels_list = []
            for item in batch:
                annotations = item.get('annotations', {})
                seq_len = len(item['sequence'])
                if seq_len > max_len:
                    seq_len = max_len
                
                item_labels = [0] * seq_len
                for pos, ann_type in annotations.items():
                    if pos <= seq_len and ann_type in ['BINDING', 'ACT_SITE', 'ACTIVE']:
                        item_labels[pos - 1] = 1  # 0-indexed
                
                # Pad
                item_labels += [0] * (max_len - len(item_labels))
                binding_labels_list.append(item_labels)
            
            binding_labels = torch.tensor(binding_labels_list, dtype=torch.long).to(self.device)
            
            return {
                'input_ids': input_ids,
                'attention_mask': attention_mask,
                'labels': binding_labels
            }
    
    def pretrain_epoch(self, dataloader, epoch: int) -> float:
        """Train one epoch of MLM pretraining."""
        self.model.train()
        total_loss = 0.0
        
        for batch_idx, batch in enumerate(dataloader):
            self.optimizer.zero_grad()
            
            # Collate batch
            batch_dict = self.collate_batch(batch, task='mlm')
            
            # Forward pass
            logits = self.model.forward_mlm(batch_dict['input_ids'], batch_dict['attention_mask'])
            
            # Compute loss (only on masked tokens)
            loss = F.cross_entropy(
                logits.view(-1, self.config['model']['vocab_size']),
                batch_dict['labels'].view(-1),
                ignore_index=-100
            )
            
            # Backward pass
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            
            if batch_idx % 10 == 0:
                print(f"Pretrain Epoch {epoch}, Batch {batch_idx}, Loss: {loss.item():.4f}")
        
        avg_loss = total_loss / len(dataloader)
        print(f"Pretrain Epoch {epoch}, Average Loss: {avg_loss:.4f}")
        return avg_loss
    
    def finetune_epoch(self, dataloader, epoch: int) -> Dict[str, float]:
        """Train one epoch of binding site classification."""
        self.model.train()
        total_loss = 0.0
        total_correct = 0
        total_tokens = 0
        
        for batch_idx, batch in enumerate(dataloader):
            self.optimizer.zero_grad()
            
            # Collate batch
            batch_dict = self.collate_batch(batch, task='classification')
            
            # Forward pass
            logits = self.model.forward_classification(batch_dict['input_ids'], batch_dict['attention_mask'])
            
            # Compute loss
            loss = F.cross_entropy(
                logits.view(-1, 2),
                batch_dict['labels'].view(-1),
                ignore_index=-100
            )
            
            # Backward pass
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            
            # Compute accuracy (only on non-padding tokens)
            mask = batch_dict['attention_mask'].view(-1) == 1
            predictions = logits.argmax(dim=-1).view(-1)[mask]
            labels = batch_dict['labels'].view(-1)[mask]
            
            total_correct += (predictions == labels).sum().item()
            total_tokens += mask.sum().item()
            
            if batch_idx % 10 == 0:
                print(f"Finetune Epoch {epoch}, Batch {batch_idx}, Loss: {loss.item():.4f}")
        
        avg_loss = total_loss / len(dataloader)
        accuracy = total_correct / total_tokens if total_tokens > 0 else 0.0
        
        print(f"Finetune Epoch {epoch}, Average Loss: {avg_loss:.4f}, Accuracy: {accuracy:.4f}")
        return {'loss': avg_loss, 'accuracy': accuracy}
    
    def predict_binding_sites(self, sequence: str) -> List[Tuple[int, float]]:
        """
        Predict binding sites for a sequence.
        Returns list of (position, probability) tuples.
        """
        self.model.eval()
        
        token_ids = self.encode_sequence(sequence)
        if len(token_ids) > self.config['model']['max_seq_len']:
            token_ids = token_ids[:self.config['model']['max_seq_len']]
        
        padded_ids = token_ids + [self.pad_token_id] * (self.config['model']['max_seq_len'] - len(token_ids))
        input_ids = torch.tensor([padded_ids], dtype=torch.long).to(self.device)
        
        attention_mask = torch.tensor([[1 if tid != self.pad_token_id else 0 for tid in padded_ids]], 
                                       dtype=torch.long).to(self.device)
        
        with torch.no_grad():
            logits = self.model.forward_classification(input_ids, attention_mask)
            probs = F.softmax(logits, dim=-1)
            binding_probs = probs[0, :, 1].cpu().tolist()  # Probability of class 1 (binding)
        
        # Return only for actual sequence positions
        results = [(i + 1, binding_probs[i]) for i in range(len(token_ids))]
        return results
    
    def score_variant(self, sequence: str, position: int, mutant_aa: str) -> float:
        """
        Score a variant using masked marginal log-likelihood.
        Higher score = more likely deleterious (lower likelihood of mutant).
        """
        self.model.eval()
        
        token_ids = self.encode_sequence(sequence)
        if position < 1 or position > len(token_ids):
            return 0.0
        
        if mutant_aa not in AA_VOCAB:
            return 0.0
        
        # Mask the position
        original_aa = token_ids[position - 1]
        token_ids[position - 1] = self.mask_token_id
        
        if len(token_ids) > self.config['model']['max_seq_len']:
            token_ids = token_ids[:self.config['model']['max_seq_len']]
        
        padded_ids = token_ids + [self.pad_token_id] * (self.config['model']['max_seq_len'] - len(token_ids))
        input_ids = torch.tensor([padded_ids], dtype=torch.long).to(self.device)
        
        attention_mask = torch.tensor([[1 if tid != self.pad_token_id else 0 for tid in padded_ids]], 
                                       dtype=torch.long).to(self.device)
        
        with torch.no_grad():
            logits = self.model.forward_mlm(input_ids, attention_mask)
            log_probs = F.log_softmax(logits, dim=-1)
            
            # Get log-likelihood of original and mutant amino acids
            original_ll = log_probs[0, position - 1, original_aa].item()
            mutant_ll = log_probs[0, position - 1, AA_VOCAB[mutant_aa]].item()
            
            # Score = negative log-likelihood ratio (higher = more deleterious)
            score = -(mutant_ll - original_ll)
        
        return score
    
    def save_model(self, path: str):
        """Save model checkpoint."""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'config': self.config
        }, path)
        print(f"Model saved to {path}")
    
    def load_model(self, path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        print(f"Model loaded from {path}")


import random  # Import at module level for mask_tokens


if __name__ == '__main__':
    # Quick test
    model = ProStructModel()
    print("Model initialized successfully")
    print(f"Total parameters: {sum(p.numel() for p in model.model.parameters()):,}")
