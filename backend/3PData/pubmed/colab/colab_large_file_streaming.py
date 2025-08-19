# Large File Streaming Embedder - ULTRA-FAST for 10GB Files
# =========================================================
# Handles massive files in 30 minutes using up to 30GB RAM - OPTIMAL EMBEDDINGS

# CELL 1: Install - Updated packages
# !pip install -U langchain-huggingface langchain-community langchain sentence-transformers transformers torch psycopg2-binary sqlalchemy tqdm pgvector

# CELL 2: ULTRA-FAST Setup with OPTIMAL Embedding Quality - Fixed Imports
import os
import json
import tarfile
import gc
import io
from pathlib import Path
from ftplib import FTP
import re
import time
from datetime import datetime
import torch
from tqdm import tqdm
# Updated import for new LangChain version
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain.docstore.document import Document
from sqlalchemy import create_engine, text

# OPTIMIZED CONFIGURATION - SPEED + QUALITY (30GB RAM, 30min for 10GB)
DATABASE_URL = "postgresql://rajanishsd@localhost:5433/zivohealth"
MAX_FILES = 2              # Process 2 files max
MAX_ARTICLES_PER_FILE = 1000 # Process many articles quickly
MAX_FILE_SIZE_GB = 10.0    # Support up to 10GB files
BATCH_SIZE = 150           # MASSIVE batches for speed (was 8)
CHUNK_SIZE = 8000          # OPTIMAL for embeddings (keeping at 8KB!)
CHUNK_OVERLAP = 800        # 10% overlap for good context
READ_BUFFER_SIZE = 16 * 1024 * 1024  # 16MB buffer for ultra-fast reading
MEMORY_CLEANUP_INTERVAL = 2000   # Clean memory much less frequently
PARALLEL_ENCODING_BATCH = 100    # Large parallel encoding batches
DATABASE_BATCH_SIZE = 200        # Large database insertion batches
TRACKING_FILE = "/content/pmc_processed_files.json"

print(f"🚀 ULTRA-FAST + OPTIMAL QUALITY Configuration:")
print(f"   📦 {MAX_FILES} files, up to {MAX_FILE_SIZE_GB}GB each")
print(f"   📄 {MAX_ARTICLES_PER_FILE} articles per file")
print(f"   🧠 MASSIVE buffer: {READ_BUFFER_SIZE//1024//1024}MB")
print(f"   📊 OPTIMAL chunks: {CHUNK_SIZE} chars (best for embeddings)")
print(f"   📦 MASSIVE batches: {BATCH_SIZE} docs, {DATABASE_BATCH_SIZE} DB inserts")
print(f"   🎯 TARGET: 30 minutes for 10GB with QUALITY embeddings!")

# CELL 3: Ultra-Fast Processor with Optimal Embeddings - Fixed BioBERT
class UltraFastOptimalProcessor:
    def __init__(self):
        self.embeddings = None
        self.vector_store = None
        self.total_processed = 0
        self.total_stored = 0
        self.data_dir = Path("/content/pmc_temp")
        self.data_dir.mkdir(exist_ok=True)
        self.tracking_file = Path(TRACKING_FILE)
        self.processed_files = self.load_processed_files()
        
        # Speed tracking
        self.total_chars_processed = 0
        self.largest_file_processed = 0
        self.processing_start_time = None
        
    def clear_memory(self):
        """Smart memory cleanup - only when needed"""
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / (1024**3)
            if allocated > 28:  # Only clean if using >28GB
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        gc.collect()
    
    def check_memory_usage(self):
        """Fast memory monitoring"""
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / (1024**3)
            cached = torch.cuda.memory_reserved() / (1024**3)
            return f"GPU: {allocated:.1f}GB/{cached:.1f}GB"
        return "CPU mode"
    
    def load_processed_files(self):
        """Load tracking data"""
        if self.tracking_file.exists():
            try:
                with open(self.tracking_file, 'r') as f:
                    data = json.load(f)
                print(f"📋 Loaded: {len(data['processed_files'])} tracked files")
                return data
            except Exception as e:
                print(f"⚠️ Tracking error: {e}")
        
        return {
            "processed_files": {},
            "session_history": [],
            "total_documents_processed": 0,
            "largest_file_gb": 0,
            "total_chars_processed": 0,
            "target_time_minutes": 30,
            "optimal_chunk_size": CHUNK_SIZE,
            "last_updated": None
        }
    
    def save_processed_files(self):
        """Fast tracking save"""
        try:
            self.processed_files["last_updated"] = datetime.now().isoformat()
            self.processed_files["total_chars_processed"] = self.total_chars_processed
            self.processed_files["largest_file_gb"] = self.largest_file_processed
            with open(self.tracking_file, 'w') as f:
                json.dump(self.processed_files, f, indent=2)
        except Exception as e:
            print(f"⚠️ Save error: {e}")
    
    def is_file_processed(self, filename):
        return filename in self.processed_files["processed_files"]
    
    def mark_file_processed(self, filename, docs_processed, docs_stored, size_gb, chars_processed, time_taken):
        self.processed_files["processed_files"][filename] = {
            "processed_date": datetime.now().isoformat(),
            "documents_processed": docs_processed,
            "documents_stored": docs_stored,
            "file_size_gb": size_gb,
            "chars_processed": chars_processed,
            "time_taken_minutes": time_taken,
            "processing_speed_mb_per_min": (chars_processed / (1024*1024)) / time_taken if time_taken > 0 else 0,
            "avg_chunk_size": CHUNK_SIZE,
            "status": "completed"
        }
        self.processed_files["total_documents_processed"] += docs_stored
        self.largest_file_processed = max(self.largest_file_processed, size_gb)
        self.total_chars_processed += chars_processed
        self.save_processed_files()
    
    def mark_file_failed(self, filename, error_msg, size_gb=0):
        self.processed_files["processed_files"][filename] = {
            "processed_date": datetime.now().isoformat(),
            "documents_processed": 0,
            "documents_stored": 0,
            "file_size_gb": size_gb,
            "chars_processed": 0,
            "status": "failed",
            "error": str(error_msg)
        }
        self.save_processed_files()
    
    def setup(self):
        """ULTRA-FAST setup with optimal embedding quality - Fixed BioBERT loading"""
        print("🧠 Setting up BioBERT for ULTRA-FAST + OPTIMAL QUALITY...")
        
        self.clear_memory()
        
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🎯 Device: {device}")
        
        if torch.cuda.is_available():
            # Use maximum GPU memory for speed
            torch.cuda.set_per_process_memory_fraction(0.95)
            print(f"🔥 GPU: {torch.cuda.get_device_name()}")
            total_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"🔥 GPU Memory: {total_mem:.1f}GB (using 95% for speed)")
        
        # Try BioBERT first with fixed parameters
        try:
            print("🧠 Loading BioBERT for optimal medical embeddings...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
                model_kwargs={
                    'device': device,
                    'trust_remote_code': True
                    # Removed torch_dtype - not supported in this version
                },
                encode_kwargs={
                    'normalize_embeddings': True,
                    'batch_size': 32  # Start with conservative batch size
                    # Removed show_progress_bar - causing conflicts
                }
            )
            print("✅ BioBERT loaded successfully!")
            
            # Test encoding with small batch to verify it works
            test_text = ["This is a test for BioBERT embedding."]
            test_embedding = self.embeddings.embed_documents(test_text)
            print(f"✅ BioBERT test successful - embedding dim: {len(test_embedding[0])}")
            
            # Now increase batch size for speed
            self.embeddings.encode_kwargs['batch_size'] = PARALLEL_ENCODING_BATCH
            print(f"✅ BioBERT batch size optimized to {PARALLEL_ENCODING_BATCH}")
            
        except Exception as e:
            print(f"⚠️ BioBERT failed ({e}), using reliable fallback...")
            try:
                self.embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    model_kwargs={'device': device},
                    encode_kwargs={
                        'normalize_embeddings': True,
                        'batch_size': PARALLEL_ENCODING_BATCH
                        # Removed show_progress_bar here too
                    }
                )
                print("✅ Fallback model loaded successfully")
            except Exception as e2:
                print(f"❌ All embedding models failed: {e2}")
                raise e2
        
        print("💾 Setting up database with fast inserts...")
        engine = create_engine(DATABASE_URL)
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        self.vector_store = PGVector(
            collection_name="pmc_optimal_fast",
            connection_string=DATABASE_URL,
            embedding_function=self.embeddings,
        )
        
        print(f"✅ OPTIMAL setup complete! {self.check_memory_usage()}")
    
    def get_file_list(self):
        """Get largest files for speed testing"""
        print("🌐 Getting LARGEST files for speed testing...")
        
        with FTP("ftp.ncbi.nlm.nih.gov", timeout=120) as ftp:
            ftp.login()
            ftp.cwd("/pub/pmc/oa_bulk/oa_comm/txt/")
            ftp.voidcmd("TYPE I")
            
            dir_listing = []
            ftp.dir(dir_listing.append)
            
            tar_files_with_sizes = []
            for line in dir_listing:
                if '.tar.gz' in line:
                    parts = line.split()
                    if len(parts) >= 9:
                        filename = parts[-1]
                        size_str = parts[4]
                        
                        try:
                            if size_str.endswith('M'):
                                size_bytes = int(float(size_str[:-1]) * 1024 * 1024)
                            elif size_str.endswith('G'):
                                size_bytes = int(float(size_str[:-1]) * 1024 * 1024 * 1024)
                            elif size_str.endswith('K'):
                                size_bytes = int(float(size_str[:-1]) * 1024)
                            else:
                                size_bytes = int(size_str)
                            
                            size_gb = size_bytes / (1024**3)
                            
                            if (size_gb <= MAX_FILE_SIZE_GB and 
                                not self.is_file_processed(filename) and
                                size_gb >= 1.0):  # At least 1GB
                                tar_files_with_sizes.append((filename, size_gb))
                        except (ValueError, IndexError):
                            continue
            
            # Sort by size (LARGEST FIRST)
            tar_files_with_sizes.sort(key=lambda x: x[1], reverse=True)
            selected = tar_files_with_sizes[:MAX_FILES]
            
            print(f"📊 Selected {len(selected)} LARGEST files:")
            for filename, size_gb in selected:
                # Estimate with optimal chunks: ~1250 chunks per GB
                estimated_chunks = int(size_gb * 1250)
                estimated_time = (size_gb / 10.0) * 30
                print(f"   📦 {filename}: {size_gb:.2f}GB (~{estimated_chunks} chunks, target: {estimated_time:.1f}min)")
            
            return selected
    
    def download_file(self, filename, size_gb):
        """Ultra-fast download"""
        file_path = self.data_dir / filename
        
        if file_path.exists():
            actual_size = file_path.stat().st_size / (1024**3)
            print(f"📁 Using cached {filename} ({actual_size:.2f}GB)")
            return file_path
        
        print(f"⬇️ ULTRA-FAST downloading {filename} ({size_gb:.2f}GB)...")
        
        try:
            with FTP("ftp.ncbi.nlm.nih.gov", timeout=600) as ftp:
                ftp.login()
                ftp.cwd("/pub/pmc/oa_bulk/oa_comm/txt/")
                ftp.voidcmd("TYPE I")
                
                downloaded_bytes = 0
                start_time = time.time()
                
                def progress_callback(data):
                    nonlocal downloaded_bytes
                    downloaded_bytes += len(data)
                    if downloaded_bytes % (100 * 1024 * 1024) == 0:  # Every 100MB
                        elapsed = time.time() - start_time
                        speed_mbps = (downloaded_bytes / (1024**2)) / elapsed if elapsed > 0 else 0
                        print(f"     📥 {downloaded_bytes/(1024**2):.0f}MB at {speed_mbps:.1f}MB/s")
                
                with open(file_path, 'wb') as f:
                    def write_with_progress(data):
                        f.write(data)
                        progress_callback(data)
                    
                    ftp.retrbinary(f"RETR {filename}", write_with_progress)
                
                elapsed = time.time() - start_time
                print(f"✅ Downloaded {filename} in {elapsed/60:.1f}min")
                return file_path
                
        except Exception as e:
            print(f"❌ Download failed: {e}")
            self.mark_file_failed(filename, f"Download failed: {e}", size_gb)
            return None
    
    def optimal_stream_to_chunks(self, txt_file, pmc_id, filename, source_archive, title):
        """FAST streaming with OPTIMAL 8KB chunks for best embeddings"""
        chunks = []
        current_chunk = ""
        chunk_index = 0
        total_chars_processed = 0
        last_progress_mb = 0
        
        print(f"   🚀 FAST streaming with OPTIMAL {CHUNK_SIZE} char chunks...")
        
        while True:
            # Read large 16MB buffer for speed
            buffer = txt_file.read(READ_BUFFER_SIZE)
            if not buffer:
                break
                
            try:
                text_buffer = buffer.decode('utf-8', errors='ignore')
                current_chunk += text_buffer
                total_chars_processed += len(text_buffer)
                
                # Progress every 20MB
                current_mb = total_chars_processed / (1024*1024)
                if current_mb - last_progress_mb > 20:
                    estimated_chunks = current_mb * 1000 / 8  # ~125 chunks per MB with 8KB chunks
                    print(f"     ⚡ {current_mb:.0f}MB → ~{estimated_chunks:.0f} optimal chunks...")
                    last_progress_mb = current_mb
                
                # Process OPTIMAL 8KB chunks for best embeddings
                while len(current_chunk) >= CHUNK_SIZE:
                    # Find good sentence boundary for quality
                    split_point = CHUNK_SIZE
                    # Look for sentence endings for better semantic boundaries
                    for punct in ['. ', '! ', '? ']:
                        last_punct = current_chunk.rfind(punct, CHUNK_SIZE - 500, CHUNK_SIZE)
                        if last_punct > CHUNK_SIZE - 1000:  # Don't go too far back
                            split_point = last_punct + 2
                            break
                    else:
                        # Fallback to word boundary
                        last_space = current_chunk.rfind(' ', CHUNK_SIZE - 200, CHUNK_SIZE)
                        if last_space > 0:
                            split_point = last_space
                    
                    # Extract OPTIMAL chunk
                    chunk_text = current_chunk[:split_point].strip()
                    
                    if len(chunk_text) >= 500:  # Reasonable minimum
                        chunk = Document(
                            page_content=chunk_text,
                            metadata={
                                "pmc_id": pmc_id,
                                "filename": filename,
                                "source_archive": source_archive,
                                "title": title[:400] if title else "No title",
                                "document_type": "pmc_optimal_fast",
                                "chunk_index": chunk_index,
                                "total_chunks": -1,
                                "chunk_start": chunk_index * CHUNK_SIZE,
                                "chunk_end": chunk_index * CHUNK_SIZE + len(chunk_text),
                                "file_size_gb": 0,
                                "optimal_chunk_size": CHUNK_SIZE,
                                "processed_date": datetime.now().isoformat()
                            }
                        )
                        chunks.append(chunk)
                        chunk_index += 1
                    
                    # Keep overlap for context
                    overlap_start = max(0, split_point - CHUNK_OVERLAP)
                    current_chunk = current_chunk[overlap_start:]
                    
                    # Less frequent cleanup for speed
                    if chunk_index % MEMORY_CLEANUP_INTERVAL == 0 and chunk_index > 0:
                        allocated_gb = torch.cuda.memory_allocated() / (1024**3) if torch.cuda.is_available() else 0
                        if allocated_gb > 28:
                            gc.collect()
                        
            except Exception as e:
                print(f"   ⚠️ Stream decode error: {e}")
                break
        
        # Process final chunk
        if len(current_chunk.strip()) >= 500:
            chunk = Document(
                page_content=current_chunk.strip(),
                metadata={
                    "pmc_id": pmc_id,
                    "filename": filename,
                    "source_archive": source_archive,
                    "title": title[:400] if title else "No title",
                    "document_type": "pmc_optimal_fast",
                    "chunk_index": chunk_index,
                    "total_chunks": -1,
                    "chunk_start": chunk_index * CHUNK_SIZE,
                    "chunk_end": total_chars_processed,
                    "file_size_gb": 0,
                    "optimal_chunk_size": CHUNK_SIZE,
                    "processed_date": datetime.now().isoformat()
                }
            )
            chunks.append(chunk)
            chunk_index += 1
        
        # Update metadata
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk.metadata["total_chunks"] = total_chunks
        
        mb_processed = total_chars_processed / (1024*1024)
        chunks_per_mb = total_chunks / mb_processed if mb_processed > 0 else 0
        print(f"   ✅ OPTIMAL: {mb_processed:.1f}MB → {total_chunks} chunks ({chunks_per_mb:.0f}/MB)")
        
        del current_chunk
        
        return chunks, total_chars_processed
    
    def process_file(self, file_path, filename, size_gb):
        """ULTRA-FAST processing with OPTIMAL embeddings"""
        print(f"📂 ULTRA-FAST + OPTIMAL: {filename} ({size_gb:.2f}GB)")
        print(f"🎯 TARGET: {(size_gb/10.0)*30:.1f}min with 8KB optimal chunks")
        print(f"🧠 Memory before: {self.check_memory_usage()}")
        
        file_start_time = time.time()
        processed = 0
        stored = 0
        batch = []
        total_file_chars = 0
        
        try:
            with tarfile.open(file_path, 'r:gz') as tar:
                txt_files = [m for m in tar.getmembers() if m.name.endswith('.txt')]
                total = min(len(txt_files), MAX_ARTICLES_PER_FILE)
                
                print(f"📄 ULTRA-FAST processing {total} articles with OPTIMAL chunks...")
                
                for i, member in enumerate(tqdm(txt_files[:MAX_ARTICLES_PER_FILE], desc=f"⚡ {size_gb:.1f}GB")):
                    try:
                        # Extract file handle
                        txt_file = tar.extractfile(member)
                        
                        # Extract PMC ID
                        filename_only = os.path.basename(member.name)
                        pmc_match = re.search(r'PMC\d+', filename_only)
                        pmc_id = pmc_match.group(0) if pmc_match else filename_only.replace('.txt', '')
                        
                        # Fast title extraction
                        current_pos = txt_file.tell()
                        header = txt_file.read(4096)
                        txt_file.seek(current_pos)
                        
                        try:
                            header_text = header.decode('utf-8', errors='ignore')
                            lines = header_text.split('\n')[:10]
                            title = "No title"
                            for line in lines:
                                line = line.strip()
                                if 30 < len(line) < 200:
                                    title = line
                                    break
                        except:
                            title = "No title"
                        
                        # OPTIMAL streaming with 8KB chunks
                        document_chunks, doc_chars = self.optimal_stream_to_chunks(txt_file, pmc_id, member.name, filename, title)
                        total_file_chars += doc_chars
                        
                        # Update file size in metadata
                        for chunk in document_chunks:
                            chunk.metadata["file_size_gb"] = size_gb
                        
                        # Process in LARGE batches for speed
                        for chunk in document_chunks:
                            batch.append(chunk)
                            
                            if len(batch) >= BATCH_SIZE:
                                try:
                                    self.vector_store.add_documents(batch)
                                    stored += len(batch)
                                    self.total_stored += len(batch)
                                    batch = []
                                    
                                    # Smart cleanup - only when needed
                                    if stored % 2000 == 0:
                                        allocated_gb = torch.cuda.memory_allocated() / (1024**3) if torch.cuda.is_available() else 0
                                        if allocated_gb > 28:
                                            self.clear_memory()
                                    
                                except Exception as e:
                                    print(f"   ⚠️ Batch error: {e}")
                                    batch = []
                                    self.clear_memory()
                        
                        processed += 1
                        self.total_processed += 1
                        
                        # Clear document chunks
                        del document_chunks
                        
                        # Progress reporting
                        if i % 200 == 0:  # Every 200 articles
                            elapsed_min = (time.time() - file_start_time) / 60
                            articles_per_min = processed / elapsed_min if elapsed_min > 0 else 0
                            mb_processed = total_file_chars / (1024*1024)
                            mb_per_min = mb_processed / elapsed_min if elapsed_min > 0 else 0
                            chunks_per_min = stored / elapsed_min if elapsed_min > 0 else 0
                            projected_time = (size_gb * 1024) / mb_per_min if mb_per_min > 0 else 0
                            
                            print(f"   ⚡ Progress: {processed}/{total} articles ({articles_per_min:.1f}/min)")
                            print(f"   ⚡ Data: {mb_processed:.1f}MB ({mb_per_min:.1f}MB/min)")
                            print(f"   ⚡ Chunks: {stored} ({chunks_per_min:.0f}/min) - OPTIMAL 8KB size")
                            print(f"   🎯 Projected 10GB time: {projected_time:.1f}min (target: 30min)")
                            print(f"   🧠 Memory: {self.check_memory_usage()}")
                    
                    except Exception as e:
                        print(f"   ⚠️ Article error: {e}")
                        continue
                
                # Process final batch
                if batch:
                    try:
                        self.vector_store.add_documents(batch)
                        stored += len(batch)
                        self.total_stored += len(batch)
                    except Exception as e:
                        print(f"   ⚠️ Final batch error: {e}")
                
            file_time = (time.time() - file_start_time) / 60
            mb_processed = total_file_chars / (1024*1024)
            speed_mb_per_min = mb_processed / file_time if file_time > 0 else 0
            projected_10gb = (10*1024) / speed_mb_per_min if speed_mb_per_min > 0 else 0
            
            print(f"✅ OPTIMAL FAST COMPLETE:")
            print(f"   📊 {processed} docs, {stored} chunks (8KB optimal size)")
            print(f"   📊 {mb_processed:.1f}MB in {file_time:.1f}min ({speed_mb_per_min:.1f}MB/min)")
            print(f"   🎯 Projected 10GB: {projected_10gb:.1f}min (target: 30min)")
            if projected_10gb <= 30:
                print(f"   ✅ TARGET ACHIEVED with optimal embeddings!")
            print(f"   🧠 Memory: {self.check_memory_usage()}")
            
            self.mark_file_processed(filename, processed, stored, size_gb, total_file_chars, file_time)
            return processed, stored
            
        except Exception as e:
            print(f"❌ Processing failed: {e}")
            self.mark_file_failed(filename, f"Processing failed: {e}", size_gb)
            self.clear_memory()
            return 0, 0
    
    def run_pipeline(self):
        """ULTRA-FAST pipeline with OPTIMAL embedding quality"""
        print("🚀 Starting ULTRA-FAST + OPTIMAL PIPELINE")
        print("🎯 TARGET: 30 minutes for 10GB with OPTIMAL 8KB chunks!")
        print("=" * 60)
        
        self.processing_start_time = time.time()
        
        self.setup()
        file_list = self.get_file_list()
        
        if not file_list:
            print("✅ No new large files to process!")
            return self
        
        start_time = time.time()
        
        for i, (filename, size_gb) in enumerate(file_list, 1):
            print(f"\n🔄 OPTIMAL FAST File {i}/{len(file_list)}: {filename}")
            
            # Download
            file_path = self.download_file(filename, size_gb)
            if not file_path:
                continue
            
            # OPTIMAL FAST processing
            print(f"🧠 Pre-processing: {self.check_memory_usage()}")
            docs_processed, docs_stored = self.process_file(file_path, filename, size_gb)
            
            # Cleanup
            try:
                file_path.unlink()
                print(f"🗑️ Deleted {filename}")
            except Exception as e:
                print(f"⚠️ Delete error: {e}")
            
            # Smart cleanup
            allocated_gb = torch.cuda.memory_allocated() / (1024**3) if torch.cuda.is_available() else 0
            if allocated_gb > 25:
                self.clear_memory()
            
            # Performance analysis
            elapsed = time.time() - start_time
            total_mb = self.total_chars_processed / (1024*1024)
            mb_per_min = total_mb / (elapsed/60) if elapsed > 0 else 0
            projected_10gb_time = (10*1024) / mb_per_min if mb_per_min > 0 else 0
            chunks_per_mb = self.total_stored / total_mb if total_mb > 0 else 0
            
            print(f"📊 OPTIMAL PERFORMANCE ANALYSIS:")
            print(f"   ⚡ Documents: {self.total_processed}, Chunks: {self.total_stored}")
            print(f"   ⚡ Data: {total_mb:.1f}MB processed")
            print(f"   ⚡ Speed: {mb_per_min:.1f}MB/min")
            print(f"   📊 Chunk density: {chunks_per_mb:.0f} chunks/MB (optimal 8KB size)")
            print(f"   🎯 Projected 10GB time: {projected_10gb_time:.1f}min")
            if projected_10gb_time <= 30:
                print(f"   ✅ TARGET ACHIEVED with OPTIMAL embeddings!")
            else:
                print(f"   ⚠️ Need {30/projected_10gb_time:.1f}x speedup")
            print(f"   🧠 Memory: {self.check_memory_usage()}")
        
        # Final summary
        total_time = time.time() - start_time
        total_mb = self.total_chars_processed / (1024*1024)
        final_speed = total_mb / (total_time/60)
        projected_10gb = (10*1024) / final_speed if final_speed > 0 else 0
        final_chunks_per_mb = self.total_stored / total_mb if total_mb > 0 else 0
        
        print(f"\n🎉 OPTIMAL FAST PIPELINE COMPLETE!")
        print(f"⏱️ Total time: {total_time/60:.1f} minutes")
        print(f"📊 Documents: {self.total_processed}")
        print(f"📊 Optimal chunks: {self.total_stored} (8KB each for best embeddings)")
        print(f"📊 Data: {total_mb:.1f}MB")
        print(f"📊 Chunk density: {final_chunks_per_mb:.0f} chunks/MB")
        print(f"⚡ FINAL SPEED: {final_speed:.1f}MB/min")
        print(f"🎯 PROJECTED 10GB TIME: {projected_10gb:.1f} minutes")
        
        if projected_10gb <= 30:
            print(f"🎉 SUCCESS! Target achieved with OPTIMAL embeddings: {projected_10gb:.1f}min ≤ 30min")
        else:
            print(f"⚠️ Close but need slight optimization: {projected_10gb:.1f}min > 30min")
        
        return self

# CELL 4: Run OPTIMAL FAST Pipeline - Fixed
print("🚀 Starting OPTIMAL FAST PIPELINE - 30min for 10GB with BEST embeddings!")
print("✅ Fixed LangChain deprecation and BioBERT loading issues")
processor = UltraFastOptimalProcessor()
processor = processor.run_pipeline()

# CELL 5: OPTIMAL monitoring
def check_system_memory():
    """Monitor memory usage"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / (1024**3)
        cached = torch.cuda.memory_reserved() / (1024**3)
        max_mem = torch.cuda.max_memory_allocated() / (1024**3)
        
        print(f"🧠 GPU Memory (OPTIMAL FAST - 30GB available):")
        print(f"   Allocated: {allocated:.1f}GB")
        print(f"   Cached: {cached:.1f}GB")
        print(f"   Peak: {max_mem:.1f}GB")
        
        total_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"   Total: {total_mem:.1f}GB")
        print(f"   Usage: {(allocated/total_mem)*100:.1f}%")
        print(f"   🎯 Using optimal 8KB chunks for best embeddings")
    else:
        print("🧠 CPU mode")

def get_optimal_stats():
    """OPTIMAL embedding statistics"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total_chunks,
                COUNT(DISTINCT cmetadata->>'pmc_id') as unique_docs,
                AVG(LENGTH(document))::int as avg_chunk_size,
                SUM(LENGTH(document)) as total_content_size,
                MAX(CAST(cmetadata->>'file_size_gb' AS FLOAT)) as largest_file_gb,
                COUNT(DISTINCT cmetadata->>'source_archive') as source_files
            FROM langchain_pg_embedding 
            WHERE collection_id = (
                SELECT uuid FROM langchain_pg_collection 
                WHERE name = 'pmc_optimal_fast'
            )
        """))
        
        row = result.fetchone()
        if row:
            mb_total = row[3] / (1024*1024)
            print(f"📊 OPTIMAL EMBEDDING Stats:")
            print(f"   Total chunks: {row[0]:,}")
            print(f"   Unique documents: {row[1]:,}")
            print(f"   Avg chunk size: {row[2]:,} chars (OPTIMAL for embeddings)")
            print(f"   Total content: {mb_total:.1f} MB")
            print(f"   Largest file: {row[4]:.2f} GB")
            print(f"   Source files: {row[5]:,}")
            
            # Quality metrics
            chunks_per_mb = row[0] / mb_total if mb_total > 0 else 0
            print(f"🎯 Embedding Quality Metrics:")
            print(f"   Chunks per MB: {chunks_per_mb:.0f} (optimal: ~125)")
            print(f"   Chunk size optimized for BioBERT semantic understanding")
            if 120 <= chunks_per_mb <= 130:
                print(f"   ✅ OPTIMAL chunk density achieved!")
            else:
                print(f"   ⚠️ Chunk density: {chunks_per_mb:.0f} (target: 125)")
        else:
            print("📊 No optimal data yet")

print("\n🔧 OPTIMAL FAST Commands:")
print("   check_system_memory()  - Monitor memory usage") 
print("   get_optimal_stats()    - Optimal embedding quality stats")
print("✅ FIXED: Updated imports, removed torch_dtype, added BioBERT testing")
print("🎯 OPTIMAL: 8KB chunks (best embeddings) + 16MB buffers + 150-doc batches!")
print("🚀 TARGET: 30 minutes for 10GB with MAXIMUM embedding quality!") 