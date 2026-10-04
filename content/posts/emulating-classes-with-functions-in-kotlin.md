---
title: Emulating classes with functions in Kotlin
date: '2024-10-07T04:59:46Z'
draft: false
original_url: https://dev.to/charlietap/emulating-classes-with-functions-in-kotlin-for-maximum-performance-4fo1
---
If you're building quality software in Kotlin, you'll undoubtedly be using classes and dependency injection to ensure your code is testable.

And you'd be correct to do so! In fact, 99.9999% of the time I would say that's always the right approach to take. But sometimes it isn't... You see, there are certain drawbacks to this style of programming, more specifically drawbacks surrounding the maximum performance of your programs.

Let’s take a look

Generally, if you’re following the Single Responsibility Principle, you’ll have one class for every ‘behavior.’ Your programs become deeply nested graphs of classes composed of one another. But classes are not zero-cost abstractions; they introduce overhead, and as you’ll see later, this overhead translates to a significant number of instructions beyond the functions the classes expose. Worse still, they require allocation, which can mean a system call, increased GC pressure, and potentially an O(N) search across the heap to find an appropriate spot for their associated data.

It gets worse if your class extends an interface, this guarantees dynamic dispatch. You can think of this as another layer of indirection, it involves chasing a pointer through a v-table just so you can address the code you want to run.

You pay these aforementioned costs for every class you create, so this effect is compounding! 

There's a lot more to touch on here surrounding CPU architecture changing a lot since the _naissance_ of object oriented programming and Java but I want to keep us on track. 

Now don't panic! I said you're almost certainly doing the right thing and I mean it. In most everyday applications these overheads are in the nano/microsecond range. This delay is likely imperceivable to your customers and certainly not something you should be sacrificing the ergonomics of your codebase for!

But the project I've been working on for the past year is a bit different... 

Introducing [Chasm](https://github.com/CharlieTap/chasm). A WebAssembly interpreter built on top of Kotlin Multiplatform

Now chasm is not any old software project, it's a web assembly interpreter, and being an interpreter its goal is to translate the instructions it receives into the minimal amount of instructions for the underlying cpu.

For example in web assembly we have an instruction:

```wat
i32.add
```

and if the interpreter was doing the absolute minimum we would see something like this on ARM. 

```arm
add w0, w1, w2
```

There's actually a little bit more to this as web assembly is a stack machine and we would have to pop the operands from the stack but it's easier to explain like this.

You can imagine at some point all interpreters boil down to a loop executing an instruction.

We’re going to walk through a contrived example where we have classes and interfaces that aim to simply add two numbers. Though this is a bit silly, we should be easily able to identify the add instruction and thus recognise pretty much everything else as overhead.

Let's start with a class that's responsible for doing the adding:

```kotlin
interface Adder {
    fun add(x: Int, y: Int): Int
}

class AdderImpl: Adder {
    override fun add(x: Int, y: Int): Int = x + y
}
```

And now, let’s do some composition using dependency injection, as we normally would when writing modern Kotlin, to construct another class.

```kotlin
interface AddInstructionExecutor {
    fun add(x: Int, y: Int): Int
}

class AddInstructionExecutorImpl(
    val adder: Adder,
): AddInstructionExecutor {
    override fun add(x: Int, y: Int): Int = adder.add(x, y)
}
```

Finally let's add a main function where we construct and invoke the executor.

```kotlin
fun main(x: Int, y: Int): Int = AddInstructionExecutorImpl(AdderImpl()).add(x, y)
```

We're going to use Romain Guy's fantastic [Kotlin-Explorer](https://github.com/romainguy/kotlin-explorer) project to inspect the generated assembly. Please give it a star as it's an awesome bit of kit!

So first the AdderImpl 

![Image description](/uploads/imports/emulating-classes-with-functions-in-kotlin/f0wz21rnfd2azz1vne4m.png)


Okay not too bad, just the add instruction alongside returns for the initializer and add function. And now for the AddInstructionExecutorImpl


![Image description](/uploads/imports/emulating-classes-with-functions-in-kotlin/bre4w989w9wh6ftlie18.png)

Oof 7 instructions and 1 branch in the initializer, and 20 instructions for the add function... let's see how that affects main

![Image description](/uploads/imports/emulating-classes-with-functions-in-kotlin/e3dwxmbxm8vq3ul3uw10.png)

47 instructions and 8 branches! That's the cost we're paying for our abstraction and we're only going through two layers of indirection. You can imagine how this scales within deep dependency graphs.

So the question is can we avoid this? maintain some abstraction and keep our code testable? 

The answer is yes! kinda... there's some tradeoffs ... let's take a look

Adder implementation and interface

```kotlin
typealias FastAdder = (Int, Int) -> Int

inline fun FastAdder(x: Int, y: Int) = x + y
```

The first thing you'll notice is that we are no longer using an interface, instead we opt for a typealias. Alongside this we have swapped the class out with an inline function. If you have a keen eye there's already a tradeoff here, without a class or interface we've lost a concrete type, any function which takes two ints and returns one could satisfy our alias. 

So does it make any real difference?

![Image description](/uploads/imports/emulating-classes-with-functions-in-kotlin/6pchc66lpc85e5klx74p.png)

We've saved an instruction! That's definitely worth compromising our type system 🤣 Hold on we're getting there...

AdderInstructionExecutor implementation and interface

```kotlin
typealias FastAddInstructionExecutor = (Int, Int) -> Int

fun FastAddInstructionExecutor(
    x: Int,
    y: Int,
) = FastAddInstructionExecutor(x, y, ::FastAdder)

internal inline fun FastAddInstructionExecutor(
    x: Int,
    y: Int,
    adder: FastAdder,
) = adder(x, y)
```

So again a typealias rather than the interface but this time we have two functions oddly? the second of which is inlined? What's happening here. Well.. This is very manual dependency injection, the first function is the one you would call, without dependencies and also the function you would use in places where the typealias is expected. The second function is the actual implementation, all the dependencies are extracted into parameters so it's entirely testable. It's very important for the second function to be inline, as you'll see from the following assembly

![Image description](/uploads/imports/emulating-classes-with-functions-in-kotlin/cf73ew4frh0qmssec1gx.png)

As you can see, the function call is actually identical to FastAdder, the compiler has simply inlined it and it does nothing extra. The second function however has a lot more going on, this is because the compiler is unaware of what function will be given at runtime and thus has to deal with invoking the function reference. Fortunately this second function is unused by our program.

Finally let's turn our attention to the main function, you can probably see where this is going...

```kotlin
fun fastMain(x: Int, y: Int): Int = FastAddInstructionExecutor(x, y)
```

![Image description](/uploads/imports/emulating-classes-with-functions-in-kotlin/fznqplm0t6qxrlo8utq1.png)

Just 2 instructions! And ultimately this makes sense, everything else is just abstraction that we've added to make our program easier to maintain.


Cool! So we're able to emulate classes, perform dependency injection, and create abstractions using functions whilst achieving maximum performance. But it could get better right? After all we have the following tradeoffs:

- We've lost the unique type of the class and interface
- We are hardcoding our dependencies, potentially in multiple places
- We use two functions to emulate dependency injection, this is a bit of a song and dance

However, the ergonomics of the above approach may change in the future due to forthcoming updates to the Kotlin language. For example

**Context receivers**

Context receivers allow us to separate the "context" of a function call from its arguments. Theoretically if the compiler can resolve those dependencies and they are immutable then it may be able to provide the same inlining we see in the above approach. This is very hand wavy and probably doesn't work but kinda like this

```kotlin
@JvmInline
value class ExecutorContext(val adder: FastAdder)

context(ExecutorContext)
inline fun FastAddInstructionExecutor(
    x: Int,
    y: Int,
) = adder(x, y)
```

Anyway, I hope this breakdown brought you something new! I appreciate you're unlikely to be doing this in your day job, but think of it as another tool in your tool belt.

I wrote this post on a flight from London to Tokyo, with spotty WiFi and not a lot of sleep, you'll have to forgive any typos. I'll have a blog post out in the not too distant future talking more about the interpreter itself and how it might change the way you build your applications

Charlie