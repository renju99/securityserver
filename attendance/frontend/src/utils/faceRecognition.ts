const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/';
let modelLoadPromise: Promise<void> | null = null;
let faceApiPromise: Promise<typeof import('@vladmandic/face-api')> | null = null;

const getFaceApi = async () => {
    if (!faceApiPromise) {
        faceApiPromise = import('@vladmandic/face-api');
    }
    return faceApiPromise;
};

const getTinyFaceDetectorOptions = async () => {
    const faceapi = await getFaceApi();
    return new faceapi.TinyFaceDetectorOptions({
        inputSize: 224,
        // Slightly lower threshold improves detection on low-light/mobile cameras.
        scoreThreshold: 0.35
    });
};

export const ensureFaceModelsLoaded = async () => {
    if (!modelLoadPromise) {
        const faceapi = await getFaceApi();
        modelLoadPromise = Promise.all([
            faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
            faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
            faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
        ]).then(() => undefined);
    }
    return modelLoadPromise;
};

export const readFaceDescriptorFromVideo = async (video: HTMLVideoElement) => {
    await ensureFaceModelsLoaded();
    const faceapi = await getFaceApi();
    const detectorOptions = await getTinyFaceDetectorOptions();
    const detection = await faceapi
        .detectSingleFace(video, detectorOptions)
        .withFaceLandmarks()
        .withFaceDescriptor();

    if (!detection?.descriptor) {
        return null;
    }
    return Array.from(detection.descriptor);
};

type FacePoint = { x: number; y: number };
const distance = (a: FacePoint, b: FacePoint) => {
    const dx = a.x - b.x;
    const dy = a.y - b.y;
    return Math.sqrt(dx * dx + dy * dy);
};

const computeEyeAspectRatio = (eye: FacePoint[]) => {
    if (!eye || eye.length < 6) return 0;
    const vertical1 = distance(eye[1], eye[5]);
    const vertical2 = distance(eye[2], eye[4]);
    const horizontal = distance(eye[0], eye[3]);
    if (!horizontal) return 0;
    return (vertical1 + vertical2) / (2 * horizontal);
};

export const readFaceDescriptorWithLiveness = async (
    video: HTMLVideoElement,
    timeoutMs = 12000,
    options: { fastMode?: boolean } = {}
) => {
    await ensureFaceModelsLoaded();
    const faceapi = await getFaceApi();
    const detectorOptions = await getTinyFaceDetectorOptions();
    const started = Date.now();
    let bestDescriptor: number[] | null = null;
    let minEar = Number.POSITIVE_INFINITY;
    let maxEar = 0;
    let earSamples = 0;
    const minCaptureMs = options.fastMode ? 900 : 1400;

    const hasBlinkSignal = () => {
        const earDelta = Number.isFinite(minEar) && Number.isFinite(maxEar) ? (maxEar - minEar) : 0;
        const dynamicCloseThreshold = Number.isFinite(maxEar) ? maxEar * 0.82 : 0;
        return (
            Number.isFinite(minEar) &&
            Number.isFinite(maxEar) &&
            maxEar > 0.2 &&
            (
                // Primary threshold for clear blinks
                (minEar < 0.24 && earDelta > 0.045) ||
                // Adaptive threshold for lower-quality cameras and frame rates
                (minEar < dynamicCloseThreshold && earDelta > 0.035)
            )
        );
    };

    while (Date.now() - started < timeoutMs) {
        // eslint-disable-next-line no-await-in-loop
        const detection = await faceapi
            .detectSingleFace(video, detectorOptions)
            .withFaceLandmarks()
            .withFaceDescriptor();

        if (detection?.descriptor && detection?.landmarks) {
            bestDescriptor = Array.from(detection.descriptor);
            const leftEAR = computeEyeAspectRatio(detection.landmarks.getLeftEye());
            const rightEAR = computeEyeAspectRatio(detection.landmarks.getRightEye());
            const avgEAR = (leftEAR + rightEAR) / 2;
            if (Number.isFinite(avgEAR) && avgEAR > 0) {
                minEar = Math.min(minEar, avgEAR);
                maxEar = Math.max(maxEar, avgEAR);
                earSamples += 1;
            }
        }

        const elapsed = Date.now() - started;
        if (bestDescriptor && earSamples >= 6 && elapsed >= minCaptureMs && hasBlinkSignal()) {
            break;
        }

        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve) => setTimeout(resolve, options.fastMode ? 60 : 90));
    }

    if (!bestDescriptor) {
        throw new Error('No face detected. Keep your face centered and well-lit.');
    }

    const blinkDetected = hasBlinkSignal();

    if (!blinkDetected) {
        const guidance =
            earSamples < 8
                ? 'Keep your face closer, remove glare, and improve lighting.'
                : 'Look at the camera and blink once slowly.';
        throw new Error(`Liveness check failed. ${guidance}`);
    }

    return bestDescriptor;
};
