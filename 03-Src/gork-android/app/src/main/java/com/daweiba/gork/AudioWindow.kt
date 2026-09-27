package com.daweiba.gork

/** Bounded application window; only device ACKs advance confirmedBytes. */
class AudioWindow(private val total: Int, private val chunk: Int, private val limit: Int = 3) {
    data class Block(val start: Int, val end: Int)
    private val pending = ArrayDeque<Int>()
    var sentBytes = 0
        private set
    var confirmedBytes = 0
        private set

    init {
        require(total > 0 && total % 2 == 0 && chunk >= 2 && chunk % 2 == 0 && limit in 1..3)
    }

    val outstanding: Int get() = pending.size
    val complete: Boolean get() = confirmedBytes == total && pending.isEmpty()

    fun next(): Block? {
        if (pending.size >= limit || sentBytes == total) return null
        val start = sentBytes
        val end = (start + chunk).coerceAtMost(total)
        pending.addLast(end)
        sentBytes = end
        return Block(start, end)
    }

    fun acknowledge(nextOffset: Int): Boolean {
        val index = pending.indexOf(nextOffset)
        if (index < 0) return false
        repeat(index + 1) { pending.removeFirst() }
        confirmedBytes = nextOffset
        return true
    }
}
