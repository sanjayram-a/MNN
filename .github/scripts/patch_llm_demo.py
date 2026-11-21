"""Enable native speech output in llm_demo's interactive chat() mode.

Upstream only wires setWavformCallback()/generateWavform() inside benchmark()
(batch mode). Interactive chat() therefore prints text but never synthesizes
audio. This patch installs the same callback in chat() and runs the Talker
after every turn, writing output.wav (24 kHz) next to the executable.
"""
import sys
from pathlib import Path

path = Path("transformers/llm/engine/demo/llm_demo.cpp")
code = path.read_text(encoding="utf-8")

anchor = "    auto context = llm->getContext();\n    while (true) {\n"
setup = anchor + """#ifdef LLM_SUPPORT_AUDIO
    std::vector<float> waveform;
    llm->setWavformCallback([&](const float* ptr, size_t size, bool last_chunk) {
        if (ptr != nullptr && size > 0) {
            waveform.reserve(waveform.size() + size);
            waveform.insert(waveform.end(), ptr, ptr + size);
        }
        if (last_chunk) {
            if (!waveform.empty()) {
                auto waveform_var = MNN::Express::_Const(waveform.data(), {(int)waveform.size()},
                                                         MNN::Express::NCHW, halide_type_of<float>());
                MNN::AUDIO::save("output.wav", waveform_var, 24000);
            }
            waveform.clear();
        }
        return true;
    });
#endif
"""

call = "        llm->response(messages);\n        auto assistant_str = context->generate_str;\n"
synth = call + """        {
#ifdef LLM_SUPPORT_AUDIO
            llm->generateWavform();
            std::cout << "\\n[AUDIO_SAVED]" << std::flush;
#endif
        }
"""

if "[AUDIO_SAVED]" in code:
    print("llm_demo.cpp already patched; nothing to do")
    sys.exit(0)
if code.count(anchor) != 1:
    sys.exit("ERROR: chat() anchor not found exactly once: %r" % anchor)
if code.count(call) != 1:
    sys.exit("ERROR: response(messages) anchor not found exactly once: %r" % call)

code = code.replace(anchor, setup, 1).replace(call, synth, 1)
path.write_text(code, encoding="utf-8")
print("Patched", path)
