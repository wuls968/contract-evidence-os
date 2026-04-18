# Memory Promotion Example

1. A successful vertical-slice task writes an episodic memory through `MemoryMatrix.write`.
2. The runtime validates that record with `MemoryMatrix.validate`.
3. Promotion moves the record from `validated` to `promoted` using
   `MemoryMatrix.promote`, creating a `MemoryPromotionRecord`.
4. If later evaluation discovers contamination, `MemoryMatrix.rollback` can drop the
   record back to `validated` or `provisional`.
