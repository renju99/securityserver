const MIN_DESCRIPTOR_LENGTH = 64;
const MAX_DESCRIPTOR_LENGTH = 512;

const parseDescriptor = (value) => {
    if (!Array.isArray(value)) return null;
    if (value.length < MIN_DESCRIPTOR_LENGTH || value.length > MAX_DESCRIPTOR_LENGTH) return null;
    const parsed = value.map((entry) => Number(entry));
    if (parsed.some((entry) => !Number.isFinite(entry))) return null;
    return parsed;
};

const normalizeVector = (vector) => {
    const magnitude = Math.sqrt(vector.reduce((sum, v) => sum + (v * v), 0));
    if (!Number.isFinite(magnitude) || magnitude <= 0) return null;
    return vector.map((v) => v / magnitude);
};

const cosineSimilarity = (a, b) => {
    if (!Array.isArray(a) || !Array.isArray(b)) return null;
    if (a.length !== b.length || a.length === 0) return null;
    let dot = 0;
    for (let i = 0; i < a.length; i += 1) {
        dot += a[i] * b[i];
    }
    return dot;
};

const getThreshold = () => {
    const raw = Number.parseFloat(process.env.FACE_AUTH_SIMILARITY_THRESHOLD || '0.78');
    if (!Number.isFinite(raw)) return 0.78;
    return Math.max(0.5, Math.min(0.95, raw));
};

const compareDescriptors = (storedDescriptor, candidateDescriptor) => {
    const stored = parseDescriptor(storedDescriptor);
    const candidate = parseDescriptor(candidateDescriptor);
    if (!stored || !candidate || stored.length !== candidate.length) {
        return { ok: false, similarity: 0, threshold: getThreshold() };
    }
    const storedNorm = normalizeVector(stored);
    const candidateNorm = normalizeVector(candidate);
    if (!storedNorm || !candidateNorm) {
        return { ok: false, similarity: 0, threshold: getThreshold() };
    }
    const similarity = cosineSimilarity(storedNorm, candidateNorm);
    const threshold = getThreshold();
    return {
        ok: Number.isFinite(similarity) && similarity >= threshold,
        similarity: Number.isFinite(similarity) ? similarity : 0,
        threshold
    };
};

module.exports = {
    parseDescriptor,
    compareDescriptors
};
