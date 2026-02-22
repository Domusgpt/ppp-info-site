# POM Protocol - MVP Development Cost Analysis

## Executive Summary

This document provides a realistic cost breakdown for developing a Minimum Viable Product (MVP) of the Polytopal Orthogonal Modulation (POM) protocol, based on current market research and SBIR funding guidelines.

**Bottom Line:** A Phase 1 MVP demonstrating real-time POM modulation/demodulation on FPGA hardware can be developed for **$150,000 - $275,000**, fitting within typical SBIR Phase 1 funding limits.

---

## Funding Landscape (2024-2025)

| Agency | Phase 1 Amount | Duration | Notes |
|--------|---------------|----------|-------|
| DoD (AFWERX/MDA) | Up to $314,363 | 6 months | Best fit for defense angle |
| NSF | $275,000 | 12 months | Good for commercial/science |
| DOE | $250,000 | 9 months | Clean energy applications |
| NASA | $150,000 | 6 months | Space communications |

**Recommendation:** Apply to AFWERX with hypersonic tracking as primary use case, 6G as commercial transition path.

---

## Hardware Cost Breakdown

### Option A: Software Simulation MVP (Lowest Cost)
*Proof of algorithm only - no real-time hardware*

| Item | Cost | Quantity | Total |
|------|------|----------|-------|
| Development workstations | $3,000 | 2 | $6,000 |
| Cloud compute (GPU instances) | $500/mo | 6 mo | $3,000 |
| Software licenses (MATLAB, etc.) | $2,000 | 1 | $2,000 |
| **Hardware Subtotal** | | | **$11,000** |

### Option B: FPGA Development MVP (Recommended)
*Real-time POM processing demonstration*

| Item | Cost | Quantity | Total |
|------|------|----------|-------|
| **FPGA Development Kits** | | | |
| Xilinx VU9P Eval Kit (entry-level) | $399 | 2 | $798 |
| OR Xilinx VCU118 (high-performance) | $2,799 | 2 | $5,598 |
| OR AMD/Xilinx RFSoC ZCU216 | $12,000 | 1 | $12,000 |
| **SDR Platform** | | | |
| Ettus USRP B200 (70MHz-6GHz) | $905 | 2 | $1,810 |
| OR USRP N310 (higher performance) | $4,500 | 2 | $9,000 |
| **Test Equipment** | | | |
| Oscilloscope (4-channel, 1GHz) | $5,000 | 1 | $5,000 |
| Spectrum analyzer (rent) | $500/mo | 6 mo | $3,000 |
| Signal generator | $3,000 | 1 | $3,000 |
| **Support Hardware** | | | |
| Development workstations | $3,500 | 2 | $7,000 |
| Networking/cables/accessories | $1,000 | 1 | $1,000 |
| **Hardware Subtotal (Mid-Range)** | | | **$30,000 - $45,000** |

### Option C: Full RF/Optical Testbed (Phase 2)
*End-to-end wireless/optical link*

| Item | Cost | Quantity | Total |
|------|------|----------|-------|
| Cailabs PROTEUS OAM system | Quote req. | 1 | ~$50,000+ |
| High-power optical components | $15,000 | 1 set | $15,000 |
| RF front-end (GaN amplifiers) | $10,000 | 2 | $20,000 |
| Optical bench/alignment | $8,000 | 1 | $8,000 |
| Environmental chamber (rent) | $2,000/mo | 3 mo | $6,000 |
| **Hardware Subtotal** | | | **$100,000+** |

---

## Software & Development Costs

### FPGA Development Tools

| Tool | Cost | Notes |
|------|------|-------|
| AMD/Xilinx Vivado Design Suite | $0 - $3,000 | Free for eval boards, enterprise license needed for production |
| Vitis HLS (C/C++ to FPGA) | Included | High-level synthesis for faster development |
| MATLAB HDL Coder | $4,000 | Optional - generate FPGA code from MATLAB |
| ModelSim/Questa (simulation) | $0 - $5,000 | Free student version, commercial license for validation |

### Open Source Alternatives

| Tool | Cost | Notes |
|------|------|-------|
| GNU Radio | Free | SDR framework, works with USRP |
| OpenCL for FPGA | Free | AMD/Intel FPGA synthesis |
| Verilator | Free | Open-source Verilog simulator |
| Python/NumPy stack | Free | Already developed in this repo |

**Software Subtotal:** $0 - $12,000 (depending on tool choices)

---

## Personnel Costs

### Phase 1 Team (6 months)

| Role | Rate ($/hr) | Hours | Total |
|------|-------------|-------|-------|
| Principal Investigator (0.25 FTE) | $100 | 260 | $26,000 |
| FPGA Engineer (1.0 FTE) | $85 | 1040 | $88,400 |
| Signal Processing Engineer (0.5 FTE) | $80 | 520 | $41,600 |
| Graduate Student/Intern (1.0 FTE) | $25 | 1040 | $26,000 |
| **Personnel Subtotal** | | | **$182,000** |

### Consultant Options (Lower Cost Alternative)

| Role | Rate ($/hr) | Hours | Total |
|------|-------------|-------|-------|
| FPGA Consultant | $150 | 200 | $30,000 |
| Algorithm Verification | $125 | 100 | $12,500 |
| **Consultant Subtotal** | | | **$42,500** |

---

## Total MVP Cost Estimates

### Tier 1: Simulation-Only MVP
*Proves algorithm works, no hardware*

| Category | Cost |
|----------|------|
| Hardware (workstations) | $11,000 |
| Software | $2,000 |
| Personnel (consultants) | $42,500 |
| Overhead (15%) | $8,300 |
| **Total** | **$63,800** |

### Tier 2: FPGA Demonstration MVP (RECOMMENDED)
*Real-time processing proof on FPGA*

| Category | Cost |
|----------|------|
| Hardware (FPGA + SDR) | $35,000 |
| Software licenses | $7,000 |
| Personnel (small team) | $130,000 |
| Travel/conferences | $5,000 |
| Overhead (20%) | $35,400 |
| **Total** | **$212,400** |

### Tier 3: RF Testbed MVP
*Wireless link demonstration*

| Category | Cost |
|----------|------|
| Hardware (full RF chain) | $75,000 |
| Software licenses | $12,000 |
| Personnel (full team) | $182,000 |
| Lab rental/facilities | $15,000 |
| Travel/demos | $10,000 |
| Overhead (20%) | $58,800 |
| **Total** | **$352,800** |

---

## Recommended Phase 1 Budget

For a **DoD SBIR Phase 1** ($275,000 target):

| Category | Amount | % |
|----------|--------|---|
| Direct Labor | $140,000 | 51% |
| FPGA/SDR Hardware | $40,000 | 15% |
| Software & Tools | $10,000 | 4% |
| Test Equipment (rental) | $8,000 | 3% |
| Travel (2 site visits) | $6,000 | 2% |
| Materials & Supplies | $5,000 | 2% |
| Indirect Costs (25%) | $52,250 | 19% |
| Profit/Fee (7%) | $13,750 | 5% |
| **Total** | **$275,000** | 100% |

---

## Key Procurement Recommendations

### Must-Have for Phase 1

1. **Xilinx/AMD Zynq UltraScale+ Dev Kit** (~$3,000)
   - Combines ARM processors with FPGA fabric
   - Sufficient DSP slices for 4D distance calculations
   - Direct path to production ASIC

2. **Ettus USRP B200** (~$900)
   - Proven SDR platform
   - 70MHz-6GHz coverage
   - Great for initial RF testing

3. **MATLAB + HDL Coder** (~$8,000)
   - Rapid algorithm-to-FPGA workflow
   - Matches simulation code structure

### Nice-to-Have for Phase 1

1. **High-speed oscilloscope** (rent: $500/mo)
   - Signal integrity verification

2. **Spectrum analyzer** (rent: $500/mo)
   - RF emissions testing

3. **Environmental chamber access** (rent: $2,000/mo)
   - Temperature cycling tests

---

## Risk Mitigation

| Risk | Mitigation | Cost Impact |
|------|------------|-------------|
| FPGA timing closure | Use conservative clock rates initially | +$5,000 dev time |
| Algorithm complexity | Start with 24-cell (simpler) before 600-cell | None |
| OAM hardware delays | Use phase-only SLM initially | +$10,000 |
| Staff availability | Pre-identify consultants | +$10,000 contingency |

**Recommended Contingency:** 15% of total budget

---

## Timeline to Production

| Phase | Duration | Cost | Milestone |
|-------|----------|------|-----------|
| Phase 1 (SBIR) | 6 months | $275,000 | FPGA demo working |
| Phase 2 (SBIR) | 24 months | $1,500,000 | Integrated RF testbed |
| Phase 3 | 18 months | $3,000,000+ | Field trials |
| Production | Ongoing | $500,000/yr | First customers |

---

## Sources

- [SBIR.gov Funding Information](https://www.sbir.gov/)
- [AMD/Xilinx FPGA Evaluation Boards](https://www.xilinx.com/products/boards-and-kits.html)
- [Ettus Research USRP Products](https://www.ettus.com/products/)
- [Cailabs OAM Solutions](https://www.cailabs.com/)
- [NI Radar Engineering Guide](https://www.ni.com/en/perspectives/radar-engineers-adapt-to-hypersonic-challenges.html)
- [FSO Market Analysis - Fortune Business Insights](https://www.fortunebusinessinsights.com/free-space-optics-fso-communication-market-107891)

---

*Document Version: 1.0*
*Last Updated: December 2024*
*Prepared for: SBIR/STTR Proposal Planning*
