// Bound the decompressed stream before joining or parsing, including zip bombs.
export async function decodeJournal(raw){
 const wrapped=JSON.parse(raw);
 if(wrapped.encoding!=='ZLIB_BASE64_JOURNAL_V1')return wrapped;
 const limit=512000,n=wrapped.raw_length;
 if(!Number.isSafeInteger(n)||n<=0||n>limit||typeof wrapped.data!=='string')throw Error('JOURNAL_DECOMPRESSION_BUDGET');
 const compressed=Uint8Array.from(atob(wrapped.data),c=>c.charCodeAt(0));
 const stream=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate'));
 const reader=stream.getReader(),parts=[];let size=0;
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit){await reader.cancel();throw Error('JOURNAL_DECOMPRESSION_BUDGET');}parts.push(value);}
 if(size!==n)throw Error('JOURNAL_DECOMPRESSED_LENGTH_MISMATCH');
 const bytes=new Uint8Array(size);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.byteLength;}
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
 if(hash!==wrapped.raw_sha256)throw Error('JOURNAL_DECOMPRESSED_HASH_MISMATCH');
 return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
}
