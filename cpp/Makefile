# Makefile for finance_engine shared library
# ============================================
# WHY a Makefile?
# Make tracks file modification times. If finance_engine.cpp hasn't changed
# since the last build, `make` skips recompilation. For a single file this
# doesn't matter much, but it's good professional habit and the Dockerfile
# uses it directly.
#
# Usage:
#   make          → build libfinance.so
#   make clean    → remove build artefacts
#   make test     → build and run the quick sanity test

CXX      := g++
CXXFLAGS := -O2 -std=c++17 -Wall -Wextra -fPIC
# -std=c++17  : use C++17 features (structured bindings, if constexpr, etc.)
# -Wall        : all standard warnings
# -Wextra      : extra warnings (unused params, etc.)
# -fPIC        : Position-Independent Code — REQUIRED for shared libraries

TARGET   := libfinance.so
SRCS     := finance_engine.cpp
HEADERS  := finance_engine.h

# Default target
.PHONY: all
all: $(TARGET)

$(TARGET): $(SRCS) $(HEADERS)
	$(CXX) $(CXXFLAGS) -shared -o $@ $(SRCS)
	@echo "✅  Built $(TARGET)"

# Quick smoke-test: compile and run the test binary
.PHONY: test
test: $(TARGET) test_engine.cpp
	$(CXX) $(CXXFLAGS) -o test_engine test_engine.cpp -L. -lfinance -Wl,-rpath,.
	@echo "Running tests..."
	./test_engine

# -L.           : look for libraries in the current directory
# -lfinance     : link against libfinance.so  (note: drop "lib" prefix and ".so" suffix)
# -Wl,-rpath,. : embed the current dir as a runtime library search path
#                 so the test binary finds libfinance.so without LD_LIBRARY_PATH

.PHONY: clean
clean:
	rm -f $(TARGET) test_engine
	@echo "🧹  Cleaned"
