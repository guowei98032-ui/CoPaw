#!/usr/bin/env node
/**
 * Test script to verify summary model configuration is working
 */

import { existsSync, readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

console.log('='.repeat(60));
console.log('LCM Summary Model Configuration Test');
console.log('='.repeat(60));
console.log();

// Test 1: Check config file
console.log('Test 1: Checking lcm-config.json...');
const configPath = join(__dirname, 'lcm-config.json');
if (!existsSync(configPath)) {
  console.error('❌ FAIL: lcm-config.json not found');
  process.exit(1);
}

const config = JSON.parse(readFileSync(configPath, 'utf-8'));
console.log('✅ Config file loaded');
console.log();

// Test 2: Check llm config
console.log('Test 2: Checking llm configuration...');
if (!config.llm) {
  console.error('❌ FAIL: llm configuration missing');
  process.exit(1);
}
console.log(`   Provider: ${config.llm.provider || 'not set'}`);
console.log(`   Model: ${config.llm.model || 'not set'}`);
console.log(`   API Key: ${config.llm.apiKey ? '***' + config.llm.apiKey.slice(-8) : 'not set'}`);
console.log(`   Base URL: ${config.llm.baseUrl || 'not set'}`);
console.log('✅ LLM configuration present');
console.log();

// Test 3: Check summary config
console.log('Test 3: Checking summary configuration...');
if (config.summary) {
  console.log(`   Provider: ${config.summary.provider || 'not set (will use llm.provider)'}`);
  console.log(`   Model: ${config.summary.model || 'not set (will use llm.model)'}`);
  console.log(`   API Key: ${config.summary.apiKey ? '***' + config.summary.apiKey.slice(-8) : 'not set (will use llm.apiKey)'}`);
  console.log(`   Base URL: ${config.summary.baseUrl || 'not set (will use llm.baseUrl)'}`);
  console.log('✅ Summary configuration present');
} else {
  console.log('⚠️  WARNING: No summary configuration found');
  console.log('   Will fall back to llm configuration or environment variables');
  console.log('   To fix, add "summary" section to lcm-config.json:');
  console.log();
  console.log('   "summary": {');
  console.log('     "provider": "openai",');
  console.log('     "model": "qwen3.5-plus",');
  console.log('     "apiKey": "...",');
  console.log('     "baseUrl": "..."');
  console.log('   }');
}
console.log();

// Test 4: Check environment variables
console.log('Test 4: Checking environment variables...');
const envModel = process.env.LCM_SUMMARY_MODEL;
const envProvider = process.env.LCM_SUMMARY_PROVIDER;
if (envModel || envProvider) {
  console.log(`   LCM_SUMMARY_MODEL: ${envModel || 'not set'}`);
  console.log(`   LCM_SUMMARY_PROVIDER: ${envProvider || 'not set'}`);
  console.log('✅ Environment variables present (will override config file)');
} else {
  console.log('   LCM_SUMMARY_MODEL: not set');
  console.log('   LCM_SUMMARY_PROVIDER: not set');
  console.log('ℹ️  No environment variables set (will use config file)');
}
console.log();

// Test 5: Check lossless-claw package
console.log('Test 5: Checking lossless-claw package...');
try {
  const packagePath = join(__dirname, 'node_modules', '@martian-engineering', 'lossless-claw', 'package.json');
  if (!existsSync(packagePath)) {
    console.error('❌ FAIL: lossless-claw package not installed');
    console.log();
    console.log('To install, run:');
    console.log('   npm install @martian-engineering/lossless-claw');
    process.exit(1);
  }
  const pkg = JSON.parse(readFileSync(packagePath, 'utf-8'));
  console.log(`   Version: ${pkg.version}`);
  console.log('✅ lossless-claw package installed');
} catch (e) {
  console.error('❌ FAIL: Cannot read lossless-claw package');
  console.error(e.message);
  process.exit(1);
}
console.log();

// Test 6: Check adapter code
console.log('Test 6: Checking lcm-adapter.js modifications...');
const adapterPath = join(__dirname, 'lcm-adapter.js');
if (!existsSync(adapterPath)) {
  console.error('❌ FAIL: lcm-adapter.js not found');
  process.exit(1);
}
const adapterCode = readFileSync(adapterPath, 'utf-8');
if (adapterCode.includes('summaryConfig')) {
  console.log('✅ lcm-adapter.js has summaryConfig support');
} else {
  console.log('⚠️  WARNING: lcm-adapter.js may not have summaryConfig support');
  console.log('   Check that createLcmDependencies accepts summaryConfig parameter');
}
console.log();

// Test 7: Check index.js modifications
console.log('Test 7: Checking index.js modifications...');
const indexPath = join(__dirname, 'index.js');
if (!existsSync(indexPath)) {
  console.error('❌ FAIL: index.js not found');
  process.exit(1);
}
const indexCode = readFileSync(indexPath, 'utf-8');
if (indexCode.includes('summaryConfig') && indexCode.includes('lcmConfig.summary')) {
  console.log('✅ index.js reads and passes summary configuration');
} else {
  console.log('⚠️  WARNING: index.js may not pass summary configuration');
  console.log('   Check that getEngine passes summaryConfig to createLcmDependencies');
}
console.log();

// Summary
console.log('='.repeat(60));
console.log('Summary');
console.log('='.repeat(60));
console.log();

const hasSummaryConfig = !!config.summary;
const hasEnvVars = !!(envModel || envProvider);
const hasAdapterSupport = adapterCode.includes('summaryConfig');
const hasIndexSupport = indexCode.includes('summaryConfig') && indexCode.includes('lcmConfig.summary');

if (hasSummaryConfig || hasEnvVars) {
  console.log('✅ Configuration is present');
  if (hasSummaryConfig) {
    console.log(`   Using: lcm-config.json (model: ${config.summary.model || config.llm.model})`);
  }
  if (hasEnvVars) {
    console.log(`   Using: Environment variables (model: ${envModel || config.llm.model})`);
  }
} else {
  console.log('⚠️  WARNING: No explicit summary configuration found');
  console.log('   Will rely on fallback mechanisms in lossless-claw');
}
console.log();

if (hasAdapterSupport && hasIndexSupport) {
  console.log('✅ Code modifications are in place');
} else {
  console.log('⚠️  WARNING: Code modifications may be incomplete');
  console.log('   Please ensure lcm-adapter.js and index.js are updated');
}
console.log();

console.log('='.repeat(60));
console.log('Next Steps');
console.log('='.repeat(60));
console.log();
console.log('1. Start the LCM server:');
console.log('   npm start');
console.log();
console.log('2. Check for these log messages:');
console.log('   ✅ [LCM] Dependencies created, databasePath: ...');
console.log('   ✅ [LCM] LLM Provider: openai');
console.log('   ✅ [LCM] LLM Model: qwen3.5-plus');
console.log();
console.log('3. Test with a client request:');
console.log('   curl http://localhost:3721/health');
console.log();
console.log('4. If you still see "no summary model candidates resolved":');
console.log('   - Set environment variables:');
console.log('     set LCM_SUMMARY_MODEL=qwen3.5-plus');
console.log('     set LCM_SUMMARY_PROVIDER=openai');
console.log('   - Or check that lossless-claw can resolve the model');
console.log();
console.log('='.repeat(60));
