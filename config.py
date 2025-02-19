## Calculate Packet delay:
packetSize = 9000
networkSpeed = 1


def CalculatePacketDelay(camerasConnected):
    withEthHeaders = packetSize + 14
    camerasDelayFactor = camerasConnected - 1
    transmissionTimePerPacket = withEthHeaders * 8 / networkSpeed

    minimumPacketDelay = camerasDelayFactor * transmissionTimePerPacket
    return int(minimumPacketDelay)
