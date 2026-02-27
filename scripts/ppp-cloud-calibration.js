#!/usr/bin/env node
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import os from 'node:os';
import { dirname, resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { performance as nodePerformance } from 'node:perf_hooks';
import { createHash } from 'node:crypto';
import { execSync } from 'node:child_process';

import { CalibrationToolkit } from './CalibrationToolkit.js';
import { CalibrationDatasetBuilder } from './CalibrationDatasetBuilder.js';
import { CalibrationInsightEngine } from './CalibrationInsightEngine.js';
import { SonicGeometryEngine } from './SonicGeometryEngine.js';
import { DataMapper } from './DataMapper.js';
import { defaultMapping } from './defaultMapping.js';
import { DATA_CHANNEL_COUNT } from './constants.js';

if (typeof globalThis.performance === 'undefined' || !globalThis.performance) {
    globalThis.performance = nodePerformance;
}

const moduleDir = fileURLToPath(new URL('.', import.meta.url));
const projectRoot = resolve(moduleDir, '..');

const toRelativePath = (absolutePath) => {
    const candidate = relative(projectRoot, absolutePath);
    if (!candidate || candidate.startsWith('..')) {
        return absolutePath;
    }
    return candidate.replace(/\\/g, '/');
};

const clamp = (value, min, max) => {
    if (!Number.isFinite(value)) {
        return min;
    }
    if (value < min) {
        return min;
    }
    if (value > max) {
        return max;
    }
    return value;
};

const parseArgs = (argv) => {
    const options = {
        outDir: 'dist/cloud-calibration',
        plan: null,
        runId: process.env.PPP_RUN_ID || null,
        release: process.env.PPP_RELEASE || 'ppp-cloud-calibration',
        notes: process.env.PPP_NOTES || '',
        includeSamples: true,
        help: false
    };
    for (let index = 0; index < argv.length; index += 1) {
        const token = argv[index];
        switch (token) {
            case '--out-dir':
            case '-o':
                options.outDir = argv[index + 1];
                index += 1;
                break;
            case '--plan':
            case '-p':
                options.plan = argv[index + 1];
                index += 1;
                break;
            case '--run-id':
                options.runId = argv[index + 1];
                index += 1;
                break;
            case '--release':
                options.release = argv[index + 1];
                index += 1;
                break;
            case '--notes':
                options.notes = argv[index + 1];
                index += 1;
                break;
            case '--no-samples':
                options.includeSamples = false;
                break;
            case '--help':
            case '-h':
                options.help = true;
                break;
            default:
                break;
        }
    }
    return options;
};

const sanitizeValues = (values = []) => {
    if (!values || typeof values.length !== 'number') {
        return [];
    }
    const length = Math.min(DATA_CHANNEL_COUNT, Math.max(0, Number(values.length) || 0));
    const sanitized = new Array(length);
    for (let index = 0; index < length; index += 1) {
        const numeric = Number(values[index]);
        sanitized[index] = Number.isFinite(numeric) ? clamp(numeric, 0, 1) : 0;
    }
    return sanitized;
};

const encodeOverlay = ({
    values = [],
    uniforms = {},
    sequenceId = 'sequence',
    label = 'Sequence',
    step = 0,
    totalSteps = 1,
    summary = ''
} = {}) => {
    if (!values.length) {
        return null;
    }
    const width = 320;
    const height = 180;
    const plotHeight = height - 60;
    const plotWidth = width - 40;
    const points = values
        .map((value, index) => {
            const x = 20 + (plotWidth * (values.length === 1 ? 0.5 : index / (values.length - 1)));
            const y = 30 + plotHeight - clamp(value, 0, 1) * plotHeight;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(' ');
    const progress = totalSteps > 1 ? (step / (totalSteps - 1)) : 0;
    const uniformKeys = Object.keys(uniforms)
        .filter((key) => key.startsWith('u_'))
        .slice(0, 4);
    const uniformText = uniformKeys
        .map((key) => `${key.replace('u_', '')}:${Number(uniforms[key]).toFixed(2)}`)
        .join(' · ');
    const svg = `<?xml version="1.0" encoding="UTF-8"?>\n` +
        `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
        `<rect width="100%" height="100%" fill="#05060a"/>` +
        `<g transform="translate(0,20)" stroke="#1f8ff0" stroke-width="2" fill="none">` +
        `<polyline points="${points}" />` +
        `</g>` +
        `<text x="20" y="28" fill="#8ad3ff" font-family="monospace" font-size="14">${label}</text>` +
        `<text x="20" y="48" fill="#ffffff" font-family="monospace" font-size="12">` +
        `Frame ${step + 1}/${totalSteps} · ${(progress * 100).toFixed(1)}%</text>` +
        `<text x="20" y="68" fill="#9ff17d" font-family="monospace" font-size="12">${uniformText}</text>` +
        `<text x="20" y="160" fill="#d0d7ff" font-family="monospace" font-size="12">${summary}</text>` +
        `<text x="20" y="178" fill="#5c6b89" font-family="monospace" font-size="10">${sequenceId}</text>` +
        `</svg>`;
    return `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;
};

const hashJson = (payload) => {
    const json = `${JSON.stringify(payload, null, 2)}\n`;
    return createHash('sha256').update(json).digest('hex');
};

const getGitInfo = () => {
    const info = {
        commit: null,
        branch: null,
        isDirty: null
    };
    try {
        info.commit = execSync('git rev-parse HEAD', { cwd: projectRoot, stdio: ['ignore', 'pipe', 'ignore'] })
            .toString()
            .trim();
    } catch (error) {
        info.commit = null;
    }
    try {
        info.branch = execSync('git rev-parse --abbrev-ref HEAD', { cwd: projectRoot, stdio: ['ignore', 'pipe', 'ignore'] })
            .toString()
            .trim();
    } catch (error) {
        info.branch = null;
    }
    try {
        const status = execSync('git status --porcelain', { cwd: projectRoot, stdio: ['ignore', 'pipe', 'ignore'] })
            .toString()
            .trim();
        info.isDirty = status.length > 0;
    } catch (error) {
        info.isDirty = null;
    }
    return info;
};

const loadPlan = async (planPath) => {
    if (!planPath) {
        return null;
    }
    const resolvedPlan = resolve(projectRoot, planPath);
    const raw = await readFile(resolvedPlan, 'utf8');
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
        throw new Error('Calibration plan must be a JSON array of sequence descriptors.');
    }
    return parsed;
};

const writeJson = async (targetPath, payload) => {
    const json = `${JSON.stringify(payload, null, 2)}\n`;
    const buffer = Buffer.from(json, 'utf8');
    await writeFile(targetPath, buffer);
    return {
        format: 'json',
        bytes: buffer.length,
        sha256: createHash('sha256').update(buffer).digest('hex')
    };
};

const main = async () => {
    const options = parseArgs(process.argv.slice(2));
    if (options.help) {
        console.log('Usage: node scripts/ppp-cloud-calibration.js [--out-dir <dir>] [--plan <file>]');
        console.log('       [--run-id <id>] [--release <name>] [--notes <text>] [--no-samples]');
        console.log('Environment: PPP_RUN_ID, PPP_RELEASE, PPP_NOTES');
        return;
    }

    const runId = options.runId || `ppp-run-${Date.now()}`;
    const gitInfo = getGitInfo();
    const engine = new SonicGeometryEngine({ outputMode: 'analysis', contextFactory: null });
    await engine.enable();

    let lastFrameState = null;
    const dataMapper = new DataMapper({ mapping: defaultMapping, smoothing: 0.12 });

    const applyDataArray = (values, {
        source = 'calibration',
        uniformOverride = null,
        playbackFrame = null,
        transportOverride = null,
        analysisMetadata = null
    } = {}) => {
        const normalized = sanitizeValues(values);
        dataMapper.updateData(normalized);
        const derivedUniforms = dataMapper.getUniformSnapshot();
        const uniforms = uniformOverride && typeof uniformOverride === 'object'
            ? { ...derivedUniforms, ...uniformOverride }
            : derivedUniforms;
        const transport = {
            playing: true,
            loop: false,
            progress: playbackFrame && Number.isFinite(playbackFrame.progress)
                ? clamp(playbackFrame.progress, 0, 1)
                : 0,
            frameIndex: transportOverride && Number.isFinite(transportOverride.frameIndex)
                ? transportOverride.frameIndex
                : (playbackFrame && Number.isFinite(playbackFrame.index) ? playbackFrame.index : 0),
            frameCount: transportOverride && Number.isFinite(transportOverride.frameCount)
                ? transportOverride.frameCount
                : (playbackFrame && Number.isFinite(playbackFrame.count) ? playbackFrame.count : normalized.length),
            mode: typeof source === 'string' ? source : 'calibration'
        };
        if (transportOverride && typeof transportOverride === 'object') {
            if (Number.isFinite(transportOverride.progress)) {
                transport.progress = clamp(transportOverride.progress, 0, 1);
            }
            if (typeof transportOverride.mode === 'string') {
                transport.mode = transportOverride.mode;
            }
            transport.playing = Boolean(transportOverride.playing);
            transport.loop = Boolean(transportOverride.loop);
        }
        const metadata = {
            source: transport.mode,
            transport,
            visualUniforms: uniforms,
            derivedUniforms,
            playbackFrame,
            timestamp: performance.now()
        };
        if (analysisMetadata && typeof analysisMetadata === 'object') {
            Object.assign(metadata, analysisMetadata);
        }
        const analysis = engine.updateFromData(normalized, metadata);
        lastFrameState = {
            values: normalized,
            uniforms,
            sequenceId: analysisMetadata?.calibration?.sequenceId || transport.mode,
            label: analysisMetadata?.calibration?.sequenceId || 'calibration-sequence',
            step: analysisMetadata?.calibration?.step || 0,
            totalSteps: analysisMetadata?.calibration?.totalSteps || normalized.length,
            summary: analysis?.summary || ''
        };
        return uniforms;
    };

    const captureFrame = () => {
        if (!lastFrameState) {
            return null;
        }
        return encodeOverlay(lastFrameState);
    };

    const getSonicAnalysis = () => engine.getLastAnalysis();
    const statusMessages = [];

    const toolkit = new CalibrationToolkit({
        applyDataArray,
        captureFrame,
        getSonicAnalysis,
        onStatus: (text) => {
            statusMessages.push(text);
            console.log(`[Toolkit] ${text}`);
        }
    });

    const builder = new CalibrationDatasetBuilder({
        toolkit,
        onStatus: (text) => console.log(`[Dataset] ${text}`),
        metadata: {
            release: options.release,
            environment: 'cloud-calibration',
            generator: 'ppp-cloud-calibration.js',
            runId,
            notes: options.notes,
            git: gitInfo,
            node: process.version,
            platform: process.platform,
            arch: process.arch
        }
    });

    const plan = await loadPlan(options.plan);
    const manifest = await builder.runPlan(plan);
    if (!manifest) {
        console.error('Cloud calibration plan did not produce a manifest.');
        process.exit(1);
    }

    const summaryManifest = builder.getLastManifest({ includeSamples: false });
    const insightEngine = new CalibrationInsightEngine();
    const insights = insightEngine.analyzeManifest(manifest);
    const narrative = insightEngine.generateNarrative(insights, { maxItems: 10 });

    const resolvedOutDir = resolve(projectRoot, options.outDir);
    const manifestPath = resolve(resolvedOutDir, 'ppp-cloud-calibration-manifest.json');
    const summaryPath = resolve(resolvedOutDir, 'ppp-cloud-calibration-summary.json');
    const insightsPath = resolve(resolvedOutDir, 'ppp-cloud-calibration-insights.json');
    const runPath = resolve(resolvedOutDir, 'ppp-cloud-calibration-run.json');

    await mkdir(dirname(manifestPath), { recursive: true });

    const manifestToWrite = options.includeSamples ? manifest : summaryManifest;
    const manifestArtifact = await writeJson(manifestPath, manifestToWrite);
    const insightsArtifact = await writeJson(insightsPath, {
        generatedAt: new Date().toISOString(),
        summary: insights,
        narrative
    });

    if (!summaryManifest.metadata || typeof summaryManifest.metadata !== 'object') {
        summaryManifest.metadata = {};
    }

    summaryManifest.metadata.artifacts = {
        manifest: {
            path: toRelativePath(manifestPath),
            includesSamples: Boolean(options.includeSamples),
            ...manifestArtifact
        },
        insights: {
            path: toRelativePath(insightsPath),
            ...insightsArtifact
        }
    };

    if (statusMessages.length) {
        summaryManifest.statusLog = [...statusMessages];
    }

    summaryManifest.outputs = {
        manifest: summaryManifest.metadata.artifacts.manifest,
        summary: {
            path: toRelativePath(summaryPath),
            format: 'json'
        },
        insights: summaryManifest.metadata.artifacts.insights,
        run: {
            path: toRelativePath(runPath),
            format: 'json'
        }
    };

    await writeJson(summaryPath, summaryManifest);

    const runMetadata = {
        runId,
        startedAt: manifest?.metadata?.generatedAt || new Date().toISOString(),
        release: options.release,
        notes: options.notes,
        git: gitInfo,
        node: process.version,
        platform: process.platform,
        arch: process.arch,
        cpuCount: os.cpus().length,
        memoryGb: Number((os.totalmem() / (1024 ** 3)).toFixed(2)),
        plan: plan ? { path: options.plan, sequences: plan.length } : null,
        manifestHash: hashJson(summaryManifest || manifest)
    };

    await writeJson(runPath, runMetadata);

    console.log('Cloud calibration artifacts written to', toRelativePath(resolvedOutDir));
    console.log(`Sequences: ${summaryManifest?.totals?.sequenceCount ?? 'n/a'}`);
    console.log(`Frames: ${summaryManifest?.totals?.sampleCount ?? 'n/a'}`);
    console.log(`Dataset Score: ${Number.isFinite(summaryManifest?.score) ? summaryManifest.score.toFixed(4) : 'n/a'}`);
};

main().catch((error) => {
    console.error('Cloud calibration run failed.', error);
    process.exit(1);
});
