---
title: Interfacing with Wasm from Kotlin
date: '2025-11-08T16:52:41Z'
draft: false
original_url: https://dev.to/charlietap/interfacing-with-wasm-from-kotlin-2k2c
lastmod: '2025-12-25T09:45:37Z'
---

You may have heard you can compile Kotlin → Wasm but did you know you can call Wasm from Kotlin?

> Why would you want to do that?

It may sound odd but there are genuine reasons why you would want to do this. 

WebAssembly is a compilation target of almost every single language you can think of, Kotlin, Swift, Go, Rust, C, C# etc etc etc the list goes on. If you can interface with WebAssembly, you have the potential to access libraries from any of these languages! 

![Image description](/uploads/imports/interfacing-with-wasm-from-kotlin/f9vm1x8gylqw2mgnmysm.png)


Fancy working on an AI project but you're stuck because machine learning engineers cannot write anything else but Python? No problem compile PyTorch to a Wasm module and you're off to the races... Okay that's not actually possible yet but it will be soon!

Programming language ecosystems for the longest time have been siloed, preventing not just the sharing of code, but also knowledge and ideas. Wasm presents the opportunity to change that. In the not too distant future we will have the equivalent of npm but for wasm modules, a dependency registry which is contributed to by every programming language ecosystem in the world. Fast, memory safe libraries written in Rust, high level ergonomic libraries written in your favourite scripting language and everything in between.

> But isn't Web-Assembly for the ... Web?

Not really no, whilst it got its start as a solution in the browser WebAssembly is simply the specification of a virtual machine, you can implement that virtual machine wherever you like. Today we're going to take a look at a WebAssembly virtual machine built on top of Kotlin Multiplatform, which runs everywhere Kotlin Multiplatform does.

The library in question is one I've been working on slowly for the past 2 years, it's called [chasm](https://github.com/CharlieTap/chasm) and it makes working with Wasm incredibly simple. 

Let's dive in 

---

### First things first we need some Wasm

As mentioned Wasm is the compilation target of many languages, but rather than set up a language, its toolchain and compile a program we're going to use a Wasm module I've prepared for us.

You can download it [here](https://raw.githubusercontent.com/CharlieTap/interfacing-with-wasm-from-kotlin/main/add.wasm)

**add.wasm** is an incredibly simple wasm module which exports one function 'add', that takes two integers and you guessed it, adds them.

Go ahead and put `add.wasm` somewhere your build can see it (e.g. `src/main/resources/add.wasm` or `src/commonMain/resources/add.wasm`).

---

### Generating our interface

Chasm is at its heart a Wasm virtual machine, virtual machines tend to have low level apis and really aren't beginner friendly. For this reason Chasm also ships a Gradle plugin, the plugin simplifies things by generating a typesafe Kotlin interface which hides the lower level virtual machine api.

Add the following config to your build.gradle file and run a Gradle sync

```kotlin
// build.gradle.kts
plugins {
    // your usual plugin(s), e.g. jvm, android, kmp
    id("io.github.charlietap.chasm.gradle") version "2.0.0-1.2.0"
}

chasm {
    modules {
        create("Adder") {
            binary = layout.projectDirectory.file("src/main/resources/add.wasm")
            packageName = "com.example.wasm"
        }
    }
}
```

On sync (or build), the plugin decodes your Wasm module and inspects its public exports. Using the type information available it's able to synthesise a Kotlin interface and implementation for you to use.

If you take a look in your module's build directory you should find the following:

```kotlin
package com.example.wasm

interface Adder {
    fun add(a: Int, b: Int): Int
}
```

and

```kotlin
internal class AdderImpl(
  private val binary: ByteArray,
  ... //omitted for brevity
) : Adder {
```

Note that the concrete implementation accepts the Wasm binary at runtime. Although that might seem counterintuitive since the plugin is already configured with a binary, it’s intentional. This design lets you swap implementations at runtime: you can ship Adder v1 with your project and later download v2 to update the behaviour in-process... Yes this is legal on Android and iOS because Chasm is an interpreter.

That's it! You have everything you need and you can now instantiate your AdderImpl and call it like any other Kotlin class.

---

### What's happening under the hood

Before we dive further into the intricacies and gotchas, I want to explain a little bit about how this plugin runs your code on each platform.

It helps to distinguish between Chasm’s virtual machine API and the code generation this plugin produces. Chasm is a Kotlin Multiplatform (KMP) project that runs on the JVM and most native targets, but it doesn’t target the web directly. Browsers already provide a WebAssembly VM that unlike Chasm can JIT and AOT-compile Wasm, delivering near-native performance.

To take advantage of that, the Gradle plugin generates code against an abstract VM interface. On the JVM and native targets it uses Chasm (an interpreter). On JavaScript targets it delegates to the browser’s builtin Wasm runtime (V8, SpiderMonkey, or JavaScriptCore), inheriting their JIT/AOT compilation and performance.


---

## Gotchas, gotchas gotchas

It’d be great if everything were as simple as the Adder example, but WebAssembly is still evolving. We’re not yet at the point where you can grab any off the shelf library and interface with it from Kotlin without friction. In the next section, we’ll walk through the pitfalls you’re likely to hit and how the Wasm roadmap aims to address them.

### Let's talk Strings

![Image description](/uploads/imports/interfacing-with-wasm-from-kotlin/mr5go8qb8pm4w9mifzz5.png)

Sooner or later you’ll want to call a function that takes or returns a `String`. Here’s the catch: core WebAssembly (Wasm) has no built in string type. Different languages represent strings differently (think `&str` vs `String` in Rust, plus OS and FFI-oriented variants), so most current approaches settle on “just bytes”: UTF-8 encoded data living in linear memory.

Compilers work around this in a few common ways, typically by writing the string into module memory and returning a pointer (and sometimes a length). It’s easier to see by example.

Say you had a function like:

```kotlin
fun username(): String = "foo"
```

Some compilers will emit:

```wat
(func (export "username") (result i32 i32))
```

That’s two `i32`s: the first is a pointer to the string in memory, the second is its length.

Others will emit:

```wat
(func (export "username") (result i32))
```

So how do you know where the string ends? It depends on the calling convention. Some toolchains use null-terminated strings; others encode the length at (or just before) the pointer. The important bit is: you must know your compiler’s string encoding strategy.

The good news: Chasm has support for all of these different encoding strategies. Even if the Wasm interface uses integers under the hood, Chasm can still generate a Kotlin interface that deals in `String`. You just need to steer the config with the right encoding hint.

Assume the compiler null-terminates strings and returns a single integer:

```kotlin
chasm {
    modules {
        create("Foo") {
            binary = layout.projectDirectory.file("src/commonMain/resources/foo.wasm")
            packageName = "com.foo.bar"
            function("username") {
                stringReturnType(StringEncodingStrategy.NULL_TERMINATED)
            }
        }
    }
}
```

> So for `String` parameters we would just add `stringParam()`?

Yes... but there’s one more piece. When you pass a `String`, Chasm has to write it into the VM’s memory. To do that safely, it needs to coordinate with your Wasm module’s allocator. If your toolchain exports allocator functions, Chasm can use them.

Assuming null-terminated strings and that your module exports the classic `malloc`/`free`, you can wire up an allocator like this:

```kotlin
fun truncate(input: String): String
```

```kotlin
chasm {
    modules {
        create("Truncator") {
            binary = layout.projectDirectory.file("src/commonMain/resources/truncate.wasm")
            packageName = "com.foo.bar"
            allocator = ExportedAllocator("malloc", "free")
            function("truncate") {
                stringParam(StringEncodingStrategy.NULL_TERMINATED)
                stringReturnType(StringEncodingStrategy.NULL_TERMINATED)
            }
        }
    }
}
```

If you want to see working examples of multiple string encodings, the example project has a [particular module](https://github.com/CharlieTap/chasm/blob/acb52db6be4137aff6ab8ae998f2d9334b117a9f/example/consumer-jvm-test/build.gradle.kts) which demonstrates this.

This isn’t ideal, you can see I'm jumping through hoops to make all this work. It forces callers to understand compiler conventions, and it doesn’t work if the compiler doesn’t expose the needed behaviours (Kotlin itself is not capable of any of the above). Things get even trickier for functions that return classes/structs or other aggregate types; there’s no portable way to express those over the core ABI.

However... as mentioned before Wasm is an evolving spec and for the problems highlighted there is light at the end of the tunnel. The upcoming **[Wasm Component Model](https://component-model.bytecodealliance.org/)** proposal looks to address all of these issues.

---


## The Component Model

The Component Model is a clever proposal. It tackles the awkward reality that modules compiled from different languages have differing binary interfaces and yet we still want them to interoperate. You can’t just bolt a string type onto core Wasm and call it done; that wouldn’t help the thousands of existing modules already in the wild. So the proposal comes at the problem from two angles:

1. **Add a language-neutral type system**
This is WIT (WebAssembly Interface Types) an IDL and type system for describing functions and rich data (string, `list<T>`, records, variants, `result<T, E>`, etc.). With WIT, everyone agrees on what crosses the boundary, independent of any one compiler’s ABI.

2. **Wrap existing modules in a "component"**
A component is a new concept to WebAssembly, it's essentially a wrapper around a core Wasm module that exposes WIT defined imports/exports. The component acts as a translator speaking WIT to the outside world, and internally lifting and lowering types from modules' differing binary interfaces

The Component Model is currently a Stage 1 WebAssembly proposal. It’s been actively developed for the last few years and is inching toward standardisation. When a formal spec lands, I'll be promptly updating Chasm...

> So once the Component Model ships, will everything “just work”?

Kind of... but not by itself. The Component Model standardises type boundaries. At the start of this post we spoke about ubiquitous programming components, true universal binaries and for that to be a reality we need to talk about syscalls and operating systems.

---

## Syscalls, WASI and the elusive universal binary

WebAssembly is a specification of an abstract virtual machine, but it has no notion of an operating system. Instead the specification details a system of imports and exports. You can for example import functions from the host system, it's through this mechanism Wasm can import all the operating system functionality it needs.

> Right... but how do modules know which imports to call?

They target WASI (the WebAssembly System Interface), which is an entirely separate specification which standardises a set of OS-like capabilities as well known imports. In simple terms: the module asks for functions defined by WASI, and the host provides implementations for the current platform.

WASI is nascent in comparison to Wasm, there have been three iterations of it so far, preview 1,2 and 3 and you can infer from the naming this is not the endgame.

Preview 1 is the broadly supported baseline that works with today’s stable Wasm runtimes (Wasm 3.0). It covers file I/O, clocks, random, etc., but it lacks networking.

Preview 2 and 3 are largely complete but they unfortunately depend on types from The Component Model...

Chasm supports WASI Preview 1 today via the excellent [wasi-emscripten-host](https://github.com/illarionov/wasi-emscripten-host) but you have to wire the imports yourself. I will automate this once we get something complete that works with stable Wasm but for now I'm busy working on some other "things" I think will have more impact.

---

## Closing Thoughts

Despite all the rough edges and limitations, I think we’re trending in the right direction. Chasm makes interacting with the Wasm of today feel seamless. It’s Kotlin Multiplatform from the ground up, you can write one module and run it across web, iOS, and Android whilst programming against the same consistent interface.

For the more curious you can check out the Kotlin Multiplatform example project [here](https://github.com/CharlieTap/chasm/tree/main/example)!



