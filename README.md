# 404gen-silhouette-relief

Open-source 404-GEN subnet 17 miner for Competition 2.

This variant turns an image prompt into a compact low-poly relief model. It
samples the prompt into a small luminance grid, converts high-salience cells
into layered cuboids, and adds an outline frame and color accents. The output is
deterministic Three.js module code.

## Run

```bash
docker build -f docker/Dockerfile -t 404gen-silhouette-relief .
docker run --rm -p 10006:10006 404gen-silhouette-relief
```

## Verify

```bash
python3 -m py_compile miner_service.py generator.py verify_local.py
python3 verify_local.py
```
