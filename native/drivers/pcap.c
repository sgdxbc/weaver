#include <stdio.h>
#include <signal.h>
#include <pcap.h>
#include <stdlib.h>
#include "weaver.h"

WV_U8 ctrl_c = 0;

void ctrl_c_handler(int sig) {
    if (ctrl_c) {
        printf("shut down badly\n");
        exit(1);
    }
    printf("\nwill shut down (ctrl-c again to kill)\n");
    ctrl_c = 1;
}

typedef struct {
    WV_Runtime *runtime;
    pcap_t *pcap;
} PcapUser;

void proc(WV_Byte *user, const struct pcap_pkthdr *pcap_header, const WV_Byte *pcap_data) {
    WV_Runtime *runtime = ((PcapUser *)user)->runtime;
    WV_ByteSlice packet = { .cursor = pcap_data, .length = pcap_header->len };
    WV_U8 status = WV_ProcessPacket(packet, runtime);
    WV_ProfileRecord(runtime, pcap_header->len, status);
    if (ctrl_c) {
        pcap_breakloop(((PcapUser *)user)->pcap);
    }
}

int main(int argc, char *argv[]) {
    if (argc <= 1) {
        printf("no pcap file\n");
        return 0;
    }
    char *pcap_filename = argv[1];

    WV_Runtime runtime;
    if (WV_InitRuntime(&runtime)) {
        fprintf(stderr, "runtime initialization fail\n");
        return 1;
    }

    char errbuf[PCAP_ERRBUF_SIZE];
    pcap_t *pcap_packets = pcap_open_offline(pcap_filename, errbuf);
    if (!pcap_packets) {
        fprintf(stderr, "pcap_open_offline: %s\n", errbuf);
        return 1;
    }

    PcapUser user = { .runtime = &runtime, .pcap = pcap_packets };

    signal(SIGINT, ctrl_c_handler);
    WV_ProfileStart(&runtime);
    for (;;) {
        pcap_loop(pcap_packets, -1, proc, (void *)&user);
        if (ctrl_c) {
            break;
        }
        pcap_close(pcap_packets);
        pcap_packets = pcap_open_offline(pcap_filename, errbuf);
    }

    if (WV_CleanRuntime(&runtime)) {
        fprintf(stderr, "runtime cleanup fail\n");
        return 1;
    }

    printf("shut down correctly\n");

    return 0;
}