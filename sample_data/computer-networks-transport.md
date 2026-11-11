# Computer Networks — Transport Layer

## Role of the transport layer

The transport layer provides logical communication between processes running on different hosts.
It uses port numbers to deliver data to the correct application process, which is called multiplexing and demultiplexing.

## UDP

UDP (User Datagram Protocol) is connectionless: it sends each datagram independently with no handshake.
UDP does not guarantee delivery, ordering or duplicate protection, and it has no congestion control.
Its header is only 8 bytes, which keeps overhead low.
UDP suits applications that prefer timeliness over reliability, such as live video, online games and DNS queries.

## TCP

TCP (Transmission Control Protocol) is connection-oriented and provides a reliable, ordered byte stream.
A TCP connection is opened with a three-way handshake: SYN, SYN-ACK, then ACK.
TCP uses sequence numbers and acknowledgements, and it retransmits segments that are not acknowledged in time.
Flow control uses the receiver's advertised window so that a fast sender does not overwhelm a slow receiver.
Congestion control (for example slow start and congestion avoidance) reduces the sending rate when the network is congested.
A connection is closed with a FIN/ACK exchange in each direction.

## Choosing between TCP and UDP

Use TCP when every byte must arrive correctly and in order, such as for web pages, email and file transfer.
Use UDP when low latency matters more than occasional loss, or when the application implements its own reliability, as QUIC does.
