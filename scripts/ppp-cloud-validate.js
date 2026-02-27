#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const moduleDir = fileURLToPath(new URL('.', import.meta.url));
const projectRoot = resolve(moduleDir, '..');

const parseArgs = (argv) => {
    const options = {
        summary: 'dist/cloud-calibration/ppp-cloud-calibration-summary.json',
        run: 'dist/cloud-calibration/ppp-cloud-calibration-run.json',
        minScore: 0.6,
        checkRun: true,
        help: false
    };
    for (let index = 0; index < argv.length; index += 1) {
        const token = argv[index];
        switch (token) {
            case '--summary':
            case '-s':
                options.summary = argv[index + 1];
                index += 1;
                break;
            case '--run':
            case '-r':
                options.run = argv[index + 1];
                index += 1;
                break;
            case '--min-score':
            case '-m':
                options.minScore = Number(argv[index + 1]);
                index += 1;
                break;
            case '--no-run':
                options.checkRun = false;
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

const readJson = async (path) => {
    const resolved = resolve(projectRoot, path);
    const raw = await readFile(resolved, 'utf8');
    return JSON.parse(raw);
};

const hashJson = (payload) => {
    const json = `${JSON.stringify(payload, null, 2)}\n`;
    return createHash('sha256').update(json).digest('hex');
};

const main = async () => {
    const options = parseArgs(process.argv.slice(2));
    if (options.help) {
        console.log('Usage: node scripts/ppp-cloud-validate.js [--summary <file>] [--run <file>]');
        console.log('       [--min-score <value>] [--no-run]');
        return;
    }

    const summary = await readJson(options.summary);
    const sequences = Array.isArray(summary.sequences) ? summary.sequences : [];
    const incomplete = sequences.filter((sequence) => sequence.status !== 'complete');
    const score = Number.isFinite(summary.score) ? summary.score : null;
    const summaryHash = hashJson(summary);

    const failures = [];
    if (incomplete.length) {
        failures.push(`Incomplete sequences: ${incomplete.map((sequence) => sequence.id || sequence.label).join(', ')}`);
    }
    if (score === null) {
        failures.push('Summary score missing.');
    } else if (score < options.minScore) {
        failures.push(`Summary score ${score.toFixed(4)} below minimum ${options.minScore}.`);
    }

    if (options.checkRun) {
        const run = await readJson(options.run);
        if (run.manifestHash && run.manifestHash !== summaryHash) {
            failures.push('Run manifestHash does not match summary hash.');
        }
    }

    if (failures.length) {
        console.error('Cloud calibration validation failed:');
        failures.forEach((line) => console.error(`- ${line}`));
        process.exit(1);
    }

    console.log('Cloud calibration validation passed.');
    console.log(`Sequences: ${summary?.totals?.sequenceCount ?? sequences.length}`);
    if (score !== null) {
        console.log(`Score: ${score.toFixed(4)}`);
    }
};

main().catch((error) => {
    console.error('Cloud calibration validation failed.', error);
    process.exit(1);
});
